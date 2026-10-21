// Cloudflare Pages Advanced Worker: Handles /api/* on Cloudflare Edge

const GEMINI_MODEL = "gemini-3.8-flash";

const memorySessions = new Map();
const memoryDocuments = new Map();

function getApiKey(env) {
  return env?.GEMINI_API_KEY || "";
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

async function extractTextFromPdfBytes(arrayBuffer) {
  const bytes = new Uint8Array(arrayBuffer);
  const textDecoder = new TextDecoder("latin1");
  const rawStr = textDecoder.decode(bytes);

  let extractedText = "";
  let pageCount = 1;

  const pageMatches = rawStr.match(/\/Type\s*\/Page[^s]/g);
  if (pageMatches && pageMatches.length > 0) pageCount = pageMatches.length;

  const btRegex = /BT[\s\S]*?ET/g;
  let match;
  while ((match = btRegex.exec(rawStr)) !== null) {
    const block = match[0];
    const tjRegex = /\((.*?)\)\s*Tj/g;
    let tjMatch;
    while ((tjMatch = tjRegex.exec(block)) !== null) extractedText += tjMatch[1] + " ";
    const tjArrayRegex = /\[(.*?)\]\s*TJ/g;
    let tjArrMatch;
    while ((tjArrMatch = tjArrayRegex.exec(block)) !== null) {
      const inner = tjArrMatch[1];
      const partRegex = /\((.*?)\)/g;
      let pMatch;
      while ((pMatch = partRegex.exec(inner)) !== null) extractedText += pMatch[1];
      extractedText += " ";
    }
  }

  if (extractedText.trim().length < 50) {
    const printable = rawStr.replace(/[^\x20-\x7E\n]/g, " ").replace(/\s+/g, " ");
    extractedText = printable.slice(0, 30000);
  }

  return { text: extractedText.trim(), pageCount };
}

async function callGemini(apiKey, prompt, schema) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${apiKey}`;

  const body = {
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    generationConfig: {
      temperature: 0.2,
      responseMimeType: "application/json",
      responseSchema: schema,
    },
  };

  let lastError = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Gemini API returned ${res.status}: ${errText}`);
      }

      const data = await res.json();
      const rawText = data?.candidates?.[0]?.content?.parts?.[0]?.text;
      if (!rawText) throw new Error("Empty response from Gemini");
      return JSON.parse(rawText);
    } catch (err) {
      lastError = err;
      await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)));
    }
  }
  throw lastError;
}

async function handleApiRequest(request, env) {
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
    if (path === "/health" || path === "/api/health") {
      return jsonResponse({ status: "healthy", app: "Lumio (Cloudflare Edge)" });
    }

    if (path === "/api/sessions" && method === "POST") {
      const token = crypto.randomUUID().replace(/-/g, "");
      memorySessions.set(token, { createdAt: Date.now(), documents: new Set() });
      return jsonResponse({ session_token: token, expires_in: 3600 }, 201);
    }

    if (path === "/api/sessions/current" && method === "DELETE") {
      if (sessionToken) memorySessions.delete(sessionToken);
      return new Response(null, { status: 204 });
    }

    if (!sessionToken && path.startsWith("/api/")) {
      return errorResponse("Authentication required: missing X-Session-Token header", 401);
    }

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

      memoryDocuments.set(docId, docData);

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

    if (path.startsWith("/api/documents/") && method === "GET") {
      const docId = decodeURIComponent(path.replace("/api/documents/", ""));
      const doc = memoryDocuments.get(docId);
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

    if (path === "/api/study/deep-notes" || path === "/api/study/quick-notes") {
      const body = await request.json();
      const doc = memoryDocuments.get(body.document_id);
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

      const result = await callGemini(apiKey, prompt, schema);
      doc.materials[kind] = result;
      return jsonResponse(result);
    }

    if (path === "/api/study/quiz" && method === "POST") {
      const body = await request.json();
      const doc = memoryDocuments.get(body.document_id);
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

      const result = await callGemini(apiKey, prompt, schema);
      doc.materials["quiz"] = result;
      return jsonResponse(result);
    }

    if (path === "/api/study/flashcards" && method === "POST") {
      const body = await request.json();
      const doc = memoryDocuments.get(body.document_id);
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

      const result = await callGemini(apiKey, prompt, schema);
      doc.materials["flashcards"] = result;
      return jsonResponse(result);
    }

    if (path === "/api/chat" && method === "POST") {
      const body = await request.json();
      const doc = memoryDocuments.get(body.document_id);
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

      const result = await callGemini(apiKey, prompt, schema);
      return jsonResponse(result);
    }

    if (path === "/api/export/pdf" && method === "POST") {
      const body = await request.json();
      const doc = memoryDocuments.get(body.document_id);
      const material = doc?.materials?.[body.kind];

      const title = material?.title || `Lumio ${body.kind}`;
      let textContent = `${title}\n\n`;

      if (material?.sections) {
        for (const s of material.sections) textContent += `${s.heading}\n${s.content}\n\n`;
      } else if (material?.questions) {
        for (const q of material.questions) textContent += `Q: ${q.question}\nAnswer: ${q.answer}\nExplanation: ${q.explanation}\n\n`;
      } else if (material?.cards) {
        for (const c of material.cards) textContent += `Front: ${c.front}\nBack: ${c.back}\n\n`;
      } else {
        textContent += "Study material generated by Lumio.";
      }

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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/api/') || url.pathname === '/health') {
      return handleApiRequest(request, env);
    }
    return env.ASSETS.fetch(request);
  }
};
