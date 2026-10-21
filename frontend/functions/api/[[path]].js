// Cloudflare Pages Function: Lumio API Router powered by Groq
// Handles all /api/* requests directly on the Cloudflare Edge

const GROQ_MODEL = "openai/gpt-oss-20b";

// Global in-memory storage for active edge isolate
const memorySessions = new Map();
const memoryDocuments = new Map();

function getApiKey(env) {
  return env?.GROQ_API_KEY || "";
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, X-Session-Token",
    },
  });
}

function errorResponse(detail, status = 500) {
  return jsonResponse({ detail }, status);
}

async function getDoc(env, docId) {
  if (memoryDocuments.has(docId)) return memoryDocuments.get(docId);
  if (env?.LUMIO_STORAGE) {
    try {
      const raw = await env.LUMIO_STORAGE.get("doc:" + docId);
      if (raw) {
        const data = JSON.parse(raw);
        memoryDocuments.set(docId, data);
        return data;
      }
    } catch (_) {}
  }
  try {
    const cache = caches.default;
    const res = await cache.match(new Request(`https://lumio-internal/doc/${docId}`));
    if (res) {
      const data = await res.json();
      memoryDocuments.set(docId, data);
      return data;
    }
  } catch (_) {}
  return null;
}

async function saveDoc(env, docId, docData) {
  memoryDocuments.set(docId, docData);
  if (env?.LUMIO_STORAGE) {
    try {
      await env.LUMIO_STORAGE.put("doc:" + docId, JSON.stringify(docData), { expirationTtl: 86400 });
    } catch (_) {}
  }
  try {
    const cache = caches.default;
    await cache.put(
      new Request(`https://lumio-internal/doc/${docId}`),
      new Response(JSON.stringify(docData), { headers: { "Cache-Control": "max-age=86400" } })
    );
  } catch (_) {}
}

async function getSession(env, token) {
  if (memorySessions.has(token)) return memorySessions.get(token);
  if (env?.LUMIO_STORAGE) {
    try {
      const raw = await env.LUMIO_STORAGE.get("session:" + token);
      if (raw) {
        const data = JSON.parse(raw);
        memorySessions.set(token, data);
        return data;
      }
    } catch (_) {}
  }
  return null;
}

async function saveSession(env, token, data) {
  memorySessions.set(token, data);
  if (env?.LUMIO_STORAGE) {
    try {
      await env.LUMIO_STORAGE.put("session:" + token, JSON.stringify(data), { expirationTtl: 86400 });
    } catch (_) {}
  }
}

// Simple text extractor for uploaded PDF bytes
async function extractTextFromPdfBytes(arrayBuffer) {
  const bytes = new Uint8Array(arrayBuffer);
  const textDecoder = new TextDecoder("latin1");
  const rawStr = textDecoder.decode(bytes);

  let extractedText = "";
  let pageCount = 1;

  // Count /Type /Page
  const pageMatches = rawStr.match(/\/Type\s*\/Page[^s]/g);
  if (pageMatches && pageMatches.length > 0) {
    pageCount = pageMatches.length;
  }

  // Extract text in BT ... ET blocks
  const btRegex = /BT[\s\S]*?ET/g;
  let match;
  while ((match = btRegex.exec(rawStr)) !== null) {
    const block = match[0];
    const tjRegex = /\((.*?)\)\s*Tj/g;
    let tjMatch;
    while ((tjMatch = tjRegex.exec(block)) !== null) {
      extractedText += tjMatch[1] + " ";
    }
    const tjArrayRegex = /\[(.*?)\]\s*TJ/g;
    let tjArrMatch;
    while ((tjArrMatch = tjArrayRegex.exec(block)) !== null) {
      const inner = tjArrMatch[1];
      const partRegex = /\((.*?)\)/g;
      let pMatch;
      while ((pMatch = partRegex.exec(inner)) !== null) {
        extractedText += pMatch[1];
      }
      extractedText += " ";
    }
  }

  if (extractedText.trim().length < 50) {
    // Fallback: extract printable strings
    const printable = rawStr.replace(/[^\x20-\x7E\n]/g, " ").replace(/\s+/g, " ");
    extractedText = printable.slice(0, 30000);
  }

  return { text: extractedText.trim(), pageCount };
}

// Call Groq API with JSON Schema
async function callGroq(apiKey, prompt, schema) {
  const url = "https://api.groq.com/openai/v1/chat/completions";

  const schemaStr = typeof schema === "object" ? JSON.stringify(schema, null, 2) : String(schema);
  const systemPrompt = `You are an expert educational AI assistant. You MUST return ONLY a valid, well-formed JSON object strictly conforming to this schema:\n${schemaStr}\n\nDo NOT include markdown fences (no \`\`\`json) or any conversational text outside the JSON.`;

  const body = {
    model: GROQ_MODEL,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: prompt },
    ],
    response_format: { type: "json_object" },
    temperature: 0.2,
    max_tokens: 4096,
  };

  let lastError = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${apiKey}`,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Groq API returned ${res.status}: ${errText}`);
      }

      const data = await res.json();
      let rawText = data?.choices?.[0]?.message?.content;
      if (!rawText) throw new Error("Empty response from Groq");

      rawText = rawText.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
      return JSON.parse(rawText);
    } catch (err) {
      lastError = err;
      await new Promise((r) => setTimeout(r, 800 * (attempt + 1)));
    }
  }
  throw lastError;
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const path = url.pathname;
  const method = request.method;

  if (method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Session-Token",
      },
    });
  }

  const apiKey = getApiKey(env);
  const sessionToken = request.headers.get("X-Session-Token");

  try {
    // 1. Health check
    if (path === "/health" || path === "/api/health") {
      return jsonResponse({ status: "healthy", app: "Lumio (Cloudflare Edge with Groq)" });
    }

    // 2. Session start
    if (path === "/api/sessions" && method === "POST") {
      const token = crypto.randomUUID().replace(/-/g, "");
      await saveSession(env, token, { createdAt: Date.now(), documents: [] });
      return jsonResponse({ session_token: token, expires_in: 3600 }, 201);
    }

    // 3. Session end
    if (path === "/api/sessions/current" && method === "DELETE") {
      if (sessionToken) {
        memorySessions.delete(sessionToken);
        if (env?.LUMIO_STORAGE) {
          try { await env.LUMIO_STORAGE.delete("session:" + sessionToken); } catch (_) {}
        }
      }
      return new Response(null, { status: 204 });
    }

    // Authenticate session for document / study operations
    if (!sessionToken && path.startsWith("/api/")) {
      return errorResponse("Authentication required: missing X-Session-Token header", 401);
    }

    // 4. Document upload
    if (path === "/api/documents/upload" && method === "POST") {
      const formData = await request.formData();
      const file = formData.get("file");
      if (!file) return errorResponse("Missing file parameter in upload", 400);

      const arrayBuffer = await file.arrayBuffer();
      const { text, pageCount } = await extractTextFromPdfBytes(arrayBuffer);

      const docId = crypto.randomUUID().replace(/-/g, "");
      const chunks = [];
      const chunkSize = 1500;
      for (let i = 0; i < text.length; i += chunkSize) {
        chunks.push(text.slice(i, i + chunkSize));
      }

      const docData = {
        document_id: docId,
        filename: file.name,
        text,
        page_count: pageCount,
        chunks: chunks.length ? chunks : [text],
        materials: {},
        chat: [],
      };

      await saveDoc(env, docId, docData);

      return jsonResponse(
        {
          document_id: docId,
          filename: file.name,
          page_count: pageCount,
          sections_detected: Math.max(1, Math.min(chunks.length, 8)),
          chunks_created: chunks.length || 1,
          status: "ready",
        },
        201
      );
    }

    // 5. Get document
    if (path.startsWith("/api/documents/") && method === "GET") {
      const docId = decodeURIComponent(path.replace("/api/documents/", ""));
      const doc = await getDoc(env, docId);
      if (!doc) return errorResponse("Document not found", 404);
      return jsonResponse({
        document_id: doc.document_id,
        filename: doc.filename,
        page_count: doc.page_count,
        sections_detected: doc.chunks.length,
        chunks_created: doc.chunks.length,
        status: "ready",
      });
    }

    // 6. Deep notes & Quick notes
    if (path === "/api/study/deep-notes" || path === "/api/study/quick-notes") {
      const body = await request.json();
      const doc = await getDoc(env, body.document_id);
      if (!doc) return errorResponse("Document not found", 404);

      const isQuick = path.includes("quick-notes");
      const kind = isQuick ? "quick-notes" : "deep-notes";

      const prompt = `Create ${kind} for a student using this textbook content.
Document: ${doc.filename}
Textbook Content:
${doc.text.slice(0, 15000)}

Organize into clear sections with heading, detailed content, and source_pages (e.g. [1]).`;

      const schema = {
        type: "OBJECT",
        properties: {
          title: { type: "STRING" },
          sections: {
            type: "ARRAY",
            items: {
              type: "OBJECT",
              properties: {
                heading: { type: "STRING" },
                content: { type: "STRING" },
                source_pages: { type: "ARRAY", items: { type: "INTEGER" } },
              },
              required: ["heading", "content"],
            },
          },
        },
        required: ["title", "sections"],
      };

      const result = await callGroq(apiKey, prompt, schema);
      doc.materials[kind] = result;
      await saveDoc(env, doc.document_id, doc);
      return jsonResponse(result);
    }

    // 7. Quiz
    if (path === "/api/study/quiz" && method === "POST") {
      const body = await request.json();
      const doc = await getDoc(env, body.document_id);
      if (!doc) return errorResponse("Document not found", 404);

      const count = body.count || 5;
      const prompt = `Generate ${count} interactive quiz questions based on this textbook content.
Document: ${doc.filename}
Textbook Content:
${doc.text.slice(0, 15000)}`;

      const schema = {
        type: "OBJECT",
        properties: {
          title: { type: "STRING" },
          questions: {
            type: "ARRAY",
            items: {
              type: "OBJECT",
              properties: {
                type: { type: "STRING", enum: ["multiple_choice", "true_false", "short_answer"] },
                question: { type: "STRING" },
                options: { type: "ARRAY", items: { type: "STRING" } },
                answer: { type: "STRING" },
                explanation: { type: "STRING" },
                difficulty: { type: "STRING", enum: ["easy", "medium", "hard"] },
                source_pages: { type: "ARRAY", items: { type: "INTEGER" } },
              },
              required: ["type", "question", "options", "answer", "explanation"],
            },
          },
        },
        required: ["title", "questions"],
      };

      const result = await callGroq(apiKey, prompt, schema);
      doc.materials["quiz"] = result;
      await saveDoc(env, doc.document_id, doc);
      return jsonResponse(result);
    }

    // 8. Flashcards
    if (path === "/api/study/flashcards" && method === "POST") {
      const body = await request.json();
      const doc = await getDoc(env, body.document_id);
      if (!doc) return errorResponse("Document not found", 404);

      const prompt = `Generate focused study flashcards with front (question) and back (answer) based on this textbook:
Document: ${doc.filename}
Textbook Content:
${doc.text.slice(0, 15000)}`;

      const schema = {
        type: "OBJECT",
        properties: {
          title: { type: "STRING" },
          cards: {
            type: "ARRAY",
            items: {
              type: "OBJECT",
              properties: {
                front: { type: "STRING" },
                back: { type: "STRING" },
                source_pages: { type: "ARRAY", items: { type: "INTEGER" } },
              },
              required: ["front", "back"],
            },
          },
        },
        required: ["title", "cards"],
      };

      const result = await callGroq(apiKey, prompt, schema);
      doc.materials["flashcards"] = result;
      await saveDoc(env, doc.document_id, doc);
      return jsonResponse(result);
    }

    // 9. Chat (Ask Lumio)
    if (path === "/api/chat" && method === "POST") {
      const body = await request.json();
      const doc = await getDoc(env, body.document_id);
      if (!doc) return errorResponse("Document not found", 404);

      const question = body.question;
      const prompt = `Answer the student's question accurately using only this textbook content.
Question: ${question}
Document: ${doc.filename}
Textbook Content:
${doc.text.slice(0, 15000)}`;

      const schema = {
        type: "OBJECT",
        properties: {
          answer: { type: "STRING" },
          source_pages: { type: "ARRAY", items: { type: "INTEGER" } },
        },
        required: ["answer"],
      };

      const result = await callGroq(apiKey, prompt, schema);
      return jsonResponse(result);
    }

    // 10. PDF Export
    if (path === "/api/export/pdf" && method === "POST") {
      const body = await request.json();
      const doc = await getDoc(env, body.document_id);
      const material = doc?.materials?.[body.kind];

      const title = material?.title || `Lumio ${body.kind}`;
      let textContent = `${title}\n\n`;

      if (material?.sections) {
        for (const s of material.sections) {
          textContent += `${s.heading}\n${s.content}\n\n`;
        }
      } else if (material?.questions) {
        for (const q of material.questions) {
          textContent += `Q: ${q.question}\nAnswer: ${q.answer}\nExplanation: ${q.explanation}\n\n`;
        }
      } else if (material?.cards) {
        for (const c of material.cards) {
          textContent += `Front: ${c.front}\nBack: ${c.back}\n\n`;
        }
      } else {
        textContent += "Study material generated by Lumio.";
      }

      // Generate clean raw PDF stream
      const lines = textContent.split("\n");
      let streamText = "BT /F1 12 Tf 50 750 Td 15 TL ";
      for (const line of lines.slice(0, 45)) {
        const clean = line.replace(/[\(\)\\]/g, " ");
        streamText += `(${clean}) ' `;
      }
      streamText += "ET";

      const pdf = `%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj
4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
5 0 obj << /Length ${streamText.length} >>
stream
${streamText}
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000117 00000 n 
0000000234 00000 n 
0000000305 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
${350 + streamText.length}
%%EOF`;

      return new Response(pdf, {
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": `attachment; filename="lumio-${body.kind}.pdf"`,
        },
      });
    }

    return errorResponse(`Endpoint not found: ${path}`, 404);
  } catch (err) {
    return errorResponse(err.message || "Internal edge server error", 500);
  }
}
