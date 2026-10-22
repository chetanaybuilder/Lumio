import { inflateSync } from "node:zlib";

// Cloudflare Pages Advanced Worker: Handles /api/* on Cloudflare Edge using Cloudflare Workers AI & Groq

const GROQ_MODEL = "openai/gpt-oss-20b";

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

// ASCII85 Decoder for compressed PDF streams
function decodeAscii85(str) {
  let clean = str.replace(/\s+/g, "");
  const endIdx = clean.indexOf("~>");
  if (endIdx !== -1) clean = clean.slice(0, endIdx);
  if (clean.startsWith("<~")) clean = clean.slice(2);
  const out = [];
  for (let i = 0; i < clean.length; i += 5) {
    const chunk = clean.slice(i, i + 5);
    if (chunk === "z") {
      out.push(0, 0, 0, 0);
      continue;
    }
    const pad = 5 - chunk.length;
    let padded = chunk;
    while (padded.length < 5) padded += "u";
    let val = 0;
    for (let j = 0; j < 5; j++) {
      val = val * 85 + (padded.charCodeAt(j) - 33);
    }
    const b = [(val >>> 24) & 255, (val >>> 16) & 255, (val >>> 8) & 255, val & 255];
    out.push(...b.slice(0, 4 - pad));
  }
  return new Uint8Array(out);
}

// Clean octal and escaped characters in PDF text literals
function cleanPdfString(str) {
  return str
    .replace(/\\\\/g, "\u005C")
    .replace(/\\([0-7]{1,3})/g, (_, oct) => String.fromCharCode(parseInt(oct, 8)))
    .replace(/\\\(/g, "(")
    .replace(/\\\)/g, ")")
    .replace(/\\r/g, " ")
    .replace(/\\n/g, " ")
    .replace(/\\t/g, " ");
}

function decodeHexPdfString(hex) {
  let clean = hex.replace(/\s+/g, "");
  if (clean.length % 2 !== 0) clean += "0";
  let out = "";
  // Check if UTF-16BE (e.g. 00410042)
  if (clean.length >= 4 && clean.substr(0, 2) === "00") {
    for (let i = 0; i < clean.length; i += 4) {
      const code = parseInt(clean.substr(i, 4), 16);
      if (!isNaN(code) && code >= 32 && code <= 126) out += String.fromCharCode(code);
      else if (code === 10 || code === 13 || code === 9) out += " ";
    }
  } else {
    for (let i = 0; i < clean.length; i += 2) {
      const code = parseInt(clean.substr(i, 2), 16);
      if (!isNaN(code) && code >= 32 && code <= 126) out += String.fromCharCode(code);
      else if (code === 10 || code === 13 || code === 9) out += " ";
    }
  }
  return out;
}

// High-precision, high-speed PDF text and page extractor with robust stream matching
async function extractTextFromPdfBytes(arrayBuffer) {
  const bytes = new Uint8Array(arrayBuffer);
  const rawStr = new TextDecoder("latin1").decode(bytes);

  let pageCount = 1;
  const pageMatches = rawStr.match(/\/Type\s*\/Page[^s]/g);
  if (pageMatches && pageMatches.length > 0) {
    pageCount = pageMatches.length;
  }

  let imageCount = 0;
  let fullText = "";
  const maxChars = 150000;
  const streamRegex = /[\r\n>]stream(?:\r\n|\n)/g;
  let sm;

  while ((sm = streamRegex.exec(rawStr)) !== null && fullText.length < maxChars) {
    const streamStart = sm.index;
    const dataStart = streamRegex.lastIndex;
    const headerStart = Math.max(0, streamStart - 400);
    const headerStr = rawStr.slice(headerStart, streamStart);

    // Skip true image bitmaps and binary font streams
    const isImage = headerStr.includes("/Subtype /Image") || headerStr.includes("/Subtype/Image") || headerStr.includes("/DCTDecode") || headerStr.includes("/JPXDecode") || headerStr.includes("/JBIG2Decode");
    if (isImage) imageCount++;

    const isFont = headerStr.includes("/Type /Font") || headerStr.includes("/Type/Font") || headerStr.includes("/FontDescriptor");

    const endStream = rawStr.indexOf("endstream", dataStart);
    if (endStream === -1) break;

    if (!isImage && !isFont) {
      const streamSlice = bytes.subarray(dataStart, endStream);
      const hasAscii85 = headerStr.includes("ASCII85Decode");
      const hasFlate = headerStr.includes("FlateDecode");
      let decodedStr = null;

      try {
        if (hasAscii85 && hasFlate) {
          const asciiStr = new TextDecoder("latin1").decode(streamSlice);
          const a85 = decodeAscii85(asciiStr);
          decodedStr = new TextDecoder("latin1").decode(inflateSync(a85));
        } else if (hasFlate) {
          decodedStr = new TextDecoder("latin1").decode(inflateSync(streamSlice));
        } else if (hasAscii85) {
          const asciiStr = new TextDecoder("latin1").decode(streamSlice);
          decodedStr = new TextDecoder("latin1").decode(decodeAscii85(asciiStr));
        } else {
          decodedStr = new TextDecoder("latin1").decode(streamSlice);
        }
      } catch (_) {}

      if (decodedStr) {
        // Extract literal strings (...) Tj
        const tjRegex = /\((.*?)\)\s*Tj/g;
        let m;
        while ((m = tjRegex.exec(decodedStr)) !== null) {
          fullText += cleanPdfString(m[1]) + " ";
          if (fullText.length >= maxChars) break;
        }

        // Extract array strings [(...)] TJ
        const tjArr = /\[(.*?)\]\s*TJ/g;
        while ((m = tjArr.exec(decodedStr)) !== null) {
          const inner = m[1];
          const pRegex = /\((.*?)\)/g;
          let pm;
          while ((pm = pRegex.exec(inner)) !== null) {
            fullText += cleanPdfString(pm[1]);
          }
          const hexRegex = /<([0-9a-fA-F]+)>/g;
          while ((pm = hexRegex.exec(inner)) !== null) {
            fullText += decodeHexPdfString(pm[1]);
          }
          fullText += " ";
          if (fullText.length >= maxChars) break;
        }

        // Hex strings <...> Tj
        const hexTj = /<([0-9a-fA-F]+)>\s*Tj/g;
        while ((m = hexTj.exec(decodedStr)) !== null) {
          fullText += decodeHexPdfString(m[1]) + " ";
          if (fullText.length >= maxChars) break;
        }

        // Single and double quote operators (...) ' and aw ac (...) "
        const quoteRegex = /\((.*?)\)\s*['"]/g;
        while ((m = quoteRegex.exec(decodedStr)) !== null) {
          fullText += cleanPdfString(m[1]) + " ";
          if (fullText.length >= maxChars) break;
        }
      }
    }
  }

  // Fallback for uncompressed streams or raw text
  if (fullText.trim().length < 50) {
    const btRegex = /BT[\s\S]*?ET/g;
    let match;
    while ((match = btRegex.exec(rawStr)) !== null) {
      const block = match[0];
      const tjRegex = /\((.*?)\)\s*Tj/g;
      let tjMatch;
      while ((tjMatch = tjRegex.exec(block)) !== null) {
        fullText += cleanPdfString(tjMatch[1]) + " ";
      }
      const tjArrayRegex = /\[(.*?)\]\s*TJ/g;
      let tjArrMatch;
      while ((tjArrMatch = tjArrayRegex.exec(block)) !== null) {
        const inner = tjArrMatch[1];
        const partRegex = /\((.*?)\)/g;
        let pMatch;
        while ((pMatch = partRegex.exec(inner)) !== null) {
          fullText += cleanPdfString(pMatch[1]);
        }
        fullText += " ";
      }
    }
  }

  const cleaned = fullText.replace(/\s+/g, " ").trim();
  const isScanned = cleaned.length < 50 && imageCount > 0;
  return { text: cleaned, pageCount, isScanned, imageCount };
}

// Intelligent TF-IDF / Keyword & Diagram Context Retrieval for Ask Lumio RAG
function retrieveRelevantChunks(chunks, query, maxChars = 7000) {
  if (!chunks || chunks.length === 0) return "";
  if (chunks.length === 1) return typeof chunks[0] === "string" ? chunks[0] : chunks[0].text || "";

  const stopWords = new Set(["the", "a", "an", "is", "in", "it", "of", "and", "or", "for", "to", "on", "at", "by", "with", "about", "what", "how", "why", "who", "when", "where", "can", "tell", "me", "explain", "describe", "give"]);
  const queryTerms = query.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter(w => w.length > 2 && !stopWords.has(w));

  const scored = chunks.map((chunk, idx) => {
    const textLower = (typeof chunk === "string" ? chunk : chunk.text || "").toLowerCase();
    let score = 0;
    for (const term of queryTerms) {
      if (textLower.includes(term)) {
        const occurrences = textLower.split(term).length - 1;
        score += occurrences * 2;
        if (textLower.slice(0, 150).includes(term)) score += 5;
      }
    }
    // High-priority diagram bonus when student asks about visual elements
    const isDiagQuery = queryTerms.some(t => ["diagram", "figure", "fig", "draw", "graph", "plot", "structure", "scheme", "illustration"].includes(t));
    if (isDiagQuery && (textLower.includes("[figure") || textLower.includes("figure ") || textLower.includes("fig."))) {
      score += 15;
    }
    return { chunk: typeof chunk === "string" ? chunk : chunk.text, score, index: idx };
  });

  scored.sort((a, b) => b.score - a.score);

  const selected = [];
  let totalLen = 0;

  if (scored[0]?.score > 0) {
    for (const item of scored) {
      if (item.score > 0 && totalLen + item.chunk.length <= maxChars) {
        selected.push(item.chunk);
        totalLen += item.chunk.length;
      }
    }
  }

  if (selected.length === 0) {
    for (const c of chunks) {
      const txt = typeof c === "string" ? c : c.text;
      if (totalLen + txt.length <= maxChars) {
        selected.push(txt);
        totalLen += txt.length;
      }
    }
  }

  return selected.join("\n\n---\n\n");
}

// Build balanced, representative textbook context covering all sections and figures
function getRepresentativeContext(doc, maxChars = 7500) {
  const chunks = doc.chunks && doc.chunks.length > 0 ? doc.chunks : [doc.text || ""];
  if (chunks.length <= 6) {
    return chunks.join("\n\n---\n\n").slice(0, maxChars);
  }

  const selected = [];
  let totalLen = 0;

  // 1. Prioritize chunks with diagrams, figures, or tables
  for (let i = 0; i < chunks.length; i++) {
    const c = chunks[i];
    const textLower = (typeof c === "string" ? c : c.text || "").toLowerCase();
    if (textLower.includes("[figure") || textLower.includes("figure ") || textLower.includes("table ") || textLower.includes("| --- |")) {
      const len = typeof c === "string" ? c.length : c.text.length;
      if (!selected.includes(c) && totalLen + len <= maxChars) {
        selected.push(c);
        totalLen += len;
      }
    }
  }

  // 2. Sample evenly across all sections of the document
  const step = Math.max(1, Math.floor(chunks.length / 8));
  for (let i = 0; i < chunks.length; i += step) {
    const c = chunks[i];
    const len = typeof c === "string" ? c.length : c.text.length;
    if (!selected.includes(c) && totalLen + len <= maxChars) {
      selected.push(c);
      totalLen += len;
    }
  }

  return selected.map(c => typeof c === "string" ? c : c.text).join("\n\n---\n\n");
}

const STUDENT_ERROR_MESSAGE = "The study assistant is momentarily busy processing this textbook. Please try again in a few moments.";

// Clean and safely parse JSON from AI response
function extractJson(rawText) {
  let cleaned = rawText.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
  try {
    return JSON.parse(cleaned);
  } catch (err) {
    const firstBrace = cleaned.indexOf("{");
    const lastBrace = cleaned.lastIndexOf("}");
    if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
      return JSON.parse(cleaned.slice(firstBrace, lastBrace + 1));
    }
    throw err;
  }
}

// Call Groq API with JSON Schema
async function callGroq(apiKey, prompt, schema) {
  const url = "https://api.groq.com/openai/v1/chat/completions";

  const schemaStr = typeof schema === "object" ? JSON.stringify(schema, null, 2) : String(schema);
  const systemPrompt = `You are an expert educational AI assistant. You MUST return ONLY a valid, well-formed JSON object strictly conforming to this schema:\n${schemaStr}\n\nDo NOT include markdown fences (no \`\`\`json) or any conversational text outside the JSON.`;

  let activePrompt = prompt.length > 7000 ? prompt.slice(0, 7000) + "\n...[Context truncated]..." : prompt;
  let maxTokens = 1500;

  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const body = {
        model: GROQ_MODEL,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: activePrompt },
        ],
        response_format: { type: "json_object" },
        temperature: 0.2,
        max_tokens: maxTokens,
      };

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
        if (res.status === 413 || errText.includes("rate_limit") || errText.includes("too large")) {
          activePrompt = activePrompt.slice(0, 3500);
          maxTokens = 1000;
        }
        throw new Error(`Groq returned ${res.status}`);
      }

      const data = await res.json();
      const rawText = data?.choices?.[0]?.message?.content;
      if (!rawText) throw new Error("Empty response");
      return extractJson(rawText);
    } catch (err) {
      if (attempt === 1) throw err;
      await new Promise((r) => setTimeout(r, 600));
    }
  }
}

// Unified AI Dispatcher: Cloudflare Workers AI -> Groq Fallback -> Friendly Error
async function callAI(env, prompt, schema) {
  const schemaStr = typeof schema === "object" ? JSON.stringify(schema, null, 2) : String(schema);
  const systemPrompt = `You are an expert educational AI assistant. You MUST return ONLY a valid, well-formed JSON object strictly conforming to this schema:\n${schemaStr}\n\nDo NOT include markdown fences (no \`\`\`json) or any conversational text outside the JSON.`;

  const activePrompt = prompt.length > 7000 ? prompt.slice(0, 7000) + "\n...[Context truncated]..." : prompt;

  // 1. Primary: Cloudflare Workers AI (@cf/meta/llama-3.1-8b-instruct)
  if (env?.AI) {
    try {
      const aiRes = await env.AI.run("@cf/meta/llama-3.1-8b-instruct", {
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: activePrompt },
        ],
        max_tokens: 1500,
        temperature: 0.2,
      });

      const responseText = aiRes?.response || aiRes?.text || (typeof aiRes === "string" ? aiRes : "");
      if (responseText) {
        return extractJson(responseText);
      }
    } catch (cfError) {
      console.warn("Cloudflare Workers AI call failed, attempting fallback:", cfError?.message || cfError);
    }
  }

  // 2. Secondary fallback: Groq LPU API
  const apiKey = getApiKey(env);
  if (apiKey) {
    try {
      return await callGroq(apiKey, activePrompt, schema);
    } catch (groqError) {
      console.warn("Groq fallback call failed:", groqError?.message || groqError);
    }
  }

  // Graceful student error if daily limit or all engines are exhausted
  throw new Error(STUDENT_ERROR_MESSAGE);
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
      return jsonResponse({ status: "healthy", app: "Lumio (Cloudflare Edge with Groq)" });
    }

    if (path === "/api/sessions" && method === "POST") {
      const token = crypto.randomUUID().replace(/-/g, "");
      await saveSession(env, token, { createdAt: Date.now(), documents: [] });
      return jsonResponse({ session_token: token, expires_in: 3600 }, 201);
    }

    if (path === "/api/sessions/current" && method === "DELETE") {
      if (sessionToken) {
        memorySessions.delete(sessionToken);
        if (env?.LUMIO_STORAGE) {
          try { await env.LUMIO_STORAGE.delete("session:" + sessionToken); } catch (_) {}
        }
      }
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
      const { text, pageCount, isScanned } = await extractTextFromPdfBytes(arrayBuffer);

      if (isScanned || !text || text.trim().length < 50) {
        return errorResponse("Unable to extract readable text from this PDF. This document appears to be a scanned image or photo without selectable text. Please upload an OCR-processed or selectable textbook PDF.", 422);
      }

      const docId = crypto.randomUUID().replace(/-/g, "");
      const chunks = [];
      const chunkSize = 1200;
      const overlap = 200;
      for (let i = 0; i < text.length; i += (chunkSize - overlap)) {
        chunks.push(text.slice(i, i + chunkSize));
        if (i + chunkSize >= text.length) break;
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

    if (path === "/api/study/deep-notes" || path === "/api/study/quick-notes") {
      const body = await request.json();
      const doc = await getDoc(env, body.document_id);
      if (!doc) return errorResponse("Document not found", 404);

      const representativeText = getRepresentativeContext(doc, 7500);
      const isQuick = path.includes("quick-notes");
      const kind = isQuick ? "quick-notes" : "deep-notes";

      const prompt = isQuick
        ? `You are an elite educational AI. Create a high-yield rapid revision sheet based on this textbook content.
Document: ${doc.filename}
Textbook Excerpts:
${representativeText}

Requirements:
- 4 to 6 concise revision sections with descriptive headings.
- Include: Essential Formulas with parameter definitions, High-Priority Definitions, Crucial Scientific Distinctions, and Memory Mnemonics.
- Cite accurate source_pages.`
        : `You are an elite educational AI and master professor. Create comprehensive, in-depth study notes across all chapters and sections in this textbook.
Document: ${doc.filename}
Textbook Excerpts:
${representativeText}

Requirements:
- 5 to 8 structured, thorough sections covering the full uploaded content.
- For each section, provide: Overview, Key Definitions, Visual & Diagram Mechanisms (explicitly explaining any diagrams, figures, or structures in depth), Step-by-Step Mechanisms, Exact Formulas & Units, Worked Examples, and Exam Takeaways.
- Cite accurate source_pages.`;

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

      const result = await callAI(env, prompt, schema);
      doc.materials[kind] = result;
      await saveDoc(env, doc.document_id, doc);
      return jsonResponse(result);
    }

    if (path === "/api/study/quiz" && method === "POST") {
      const body = await request.json();
      const doc = await getDoc(env, body.document_id);
      if (!doc) return errorResponse("Document not found", 404);

      const count = body.count || 5;
      const representativeText = getRepresentativeContext(doc, 7500);
      const prompt = `You are an elite educational AI. Generate ${count} authentic interactive quiz questions based on this textbook content.
Document: ${doc.filename}
Textbook Excerpts:
${representativeText}

Requirements:
- Mix multiple_choice, true_false, and short_answer types.
- Multiple-choice questions MUST have 4 plausible, authentic options testing real conceptual understanding.
- Provide a clear question, accurate answer, detailed explanation explaining WHY the answer is correct, and valid source_pages.`;

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

      const result = await callAI(env, prompt, schema);
      doc.materials["quiz"] = result;
      await saveDoc(env, doc.document_id, doc);
      return jsonResponse(result);
    }

    if (path === "/api/study/flashcards" && method === "POST") {
      const body = await request.json();
      const doc = await getDoc(env, body.document_id);
      if (!doc) return errorResponse("Document not found", 404);

      const representativeText = getRepresentativeContext(doc, 7500);
      const prompt = `You are an elite educational AI. Generate 6 to 12 high-yield, active-recall study flashcards based on this textbook content.
Document: ${doc.filename}
Textbook Excerpts:
${representativeText}

Requirements:
- Varied card types: Definitions, Conceptual "Why/How", Diagram & Mechanism Interpretation, Formula Recall, and Common Misconceptions.
- Each card MUST have a clear "front" (question, key concept, or term to define) and a concise, complete "back" (accurate explanation, formula, or answer) with valid source_pages.`;

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

      const result = await callAI(env, prompt, schema);
      const cardsList = Array.isArray(result?.cards) ? result.cards : (Array.isArray(result?.flashcards) ? result.flashcards : []);
      const flashcardsData = {
        title: result?.title || `${doc.filename} Flashcards`,
        cards: cardsList.length ? cardsList : [
          { front: "Key Concept Review", back: "Review the textbook notes for core definitions and formulas.", source_pages: [1] }
        ],
      };
      doc.materials["flashcards"] = flashcardsData;
      await saveDoc(env, doc.document_id, doc);
      return jsonResponse(flashcardsData);
    }

    if (path === "/api/chat" && method === "POST") {
      const body = await request.json();
      const doc = await getDoc(env, body.document_id);
      if (!doc) return errorResponse("Document not found", 404);

      const question = body.question;
      const relevantContext = retrieveRelevantChunks(doc.chunks || [doc.text], question, 6500);

      const prompt = `You are Lumio, an elite, patient personal tutor grounded strictly in the student's uploaded textbook.
Answer the student's question accurately, clearly, and thoroughly based ONLY on the provided textbook excerpt.
If the student asks about a diagram, figure, or illustration, explain its visual components, step-by-step mechanism, and relation to the theory.
Explain mathematical formulas step-by-step with their units.
If the excerpt does not mention the topic at all, state honestly that the specific topic was not found in the uploaded text.

Student Question: ${question}
Document: ${doc.filename}
Relevant Textbook Content:
${relevantContext}`;

      const schema = {
        type: "OBJECT",
        properties: {
          answer: { type: "STRING" },
          source_pages: { type: "ARRAY", items: { type: "INTEGER" } },
        },
        required: ["answer"],
      };

      const result = await callAI(env, prompt, schema);
      return jsonResponse(result);
    }

    if (path === "/api/export/pdf" && method === "POST") {
      const body = await request.json();
      const doc = await getDoc(env, body.document_id);
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
    console.error("Endpoint error:", err);
    return errorResponse(STUDENT_ERROR_MESSAGE, 503);
  }
}

export async function onRequest(context) {
  return handleApiRequest(context.request, context.env);
}

export default {
  async fetch(request, env) {
    return handleApiRequest(request, env);
  },
};
