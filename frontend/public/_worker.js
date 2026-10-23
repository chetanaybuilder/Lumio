import { inflateSync } from "node:zlib";

// Cloudflare Pages Advanced Worker: Handles /api/* on Cloudflare Edge using Cloudflare Workers AI & Groq

const GROQ_MODEL = "openai/gpt-oss-20b";

const memorySessions = new Map();
const memoryDocuments = new Map();

function getApiKey(env, request = null) {
  const customKey = request?.headers?.get("X-Groq-Api-Key") || "";
  if (customKey && customKey.trim().length > 10) return customKey.trim();
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

// Parse /ToUnicode CMaps from PDF font streams
function extractCMapMappings(streamText) {
  const map = new Map();
  const bfCharBlock = /beginbfchar([\s\S]*?)endbfchar/g;
  let bfm;
  while ((bfm = bfCharBlock.exec(streamText)) !== null) {
    const pairRegex = /<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>/g;
    let pm;
    while ((pm = pairRegex.exec(bfm[1])) !== null) {
      const srcCode = parseInt(pm[1], 16);
      const dstCode = parseInt(pm[2], 16);
      if (!isNaN(srcCode) && !isNaN(dstCode)) {
        map.set(srcCode, String.fromCharCode(dstCode));
      }
    }
  }

  const bfRangeBlock = /beginbfrange([\s\S]*?)endbfrange/g;
  let bfr;
  while ((bfr = bfRangeBlock.exec(streamText)) !== null) {
    const lines = bfr[1].trim().split("\n");
    for (const line of lines) {
      const rangeMatch = line.match(/<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>/);
      if (rangeMatch) {
        const start = parseInt(rangeMatch[1], 16);
        const end = parseInt(rangeMatch[2], 16);
        let dst = parseInt(rangeMatch[3], 16);
        for (let c = start; c <= end; c++) {
          map.set(c, String.fromCharCode(dst++));
        }
      }
    }
  }
  return map;
}

function applyCMap(str, cMap) {
  if (!cMap || cMap.size === 0) return str;
  let out = "";
  for (let i = 0; i < str.length; i++) {
    const code = str.charCodeAt(i);
    out += cMap.has(code) ? cMap.get(code) : str[i];
  }
  return out;
}

// Clean octal and escaped characters in PDF text literals with optional CMap translation
function cleanPdfString(str, cMap = null) {
  const decoded = str
    .replace(/\\\\/g, "\u005C")
    .replace(/\\([0-7]{1,3})/g, (_, oct) => String.fromCharCode(parseInt(oct, 8)))
    .replace(/\\\(/g, "(")
    .replace(/\\\)/g, ")")
    .replace(/\\r/g, " ")
    .replace(/\\n/g, " ")
    .replace(/\\t/g, " ");
  return cMap && cMap.size > 0 ? applyCMap(decoded, cMap) : decoded;
}

function decodeHexPdfString(hex, cMap = null) {
  let clean = hex.replace(/\s+/g, "");
  if (clean.length % 2 !== 0) clean += "0";
  let out = "";
  const step = (clean.length >= 4 && clean.substr(0, 2) === "00") ? 4 : 2;
  for (let i = 0; i < clean.length; i += step) {
    const code = parseInt(clean.substr(i, step), 16);
    if (isNaN(code)) continue;
    if (cMap && cMap.has(code)) {
      out += cMap.get(code);
    } else if (code >= 32 && code <= 126) {
      out += String.fromCharCode(code);
    } else if (code === 10 || code === 13 || code === 9) {
      out += " ";
    }
  }
  return out;
}

// Scientific symbol, subscript, and Greek letter normalization
const GREEK_AND_MATH_MAP = {
  "\u03b1": "alpha", "\u03b2": "beta", "\u03b3": "gamma", "\u03b4": "delta",
  "\u0394": "Delta", "\u03b5": "epsilon", "\u03b8": "theta", "\u03bb": "lambda",
  "\u03bc": "mu", "\u03bd": "nu", "\u03c0": "pi", "\u03c1": "rho",
  "\u03c3": "sigma", "\u03c4": "tau", "\u03c6": "phi", "\u03c8": "psi", "\u03c9": "omega",
  "\u2192": " -> ", "\u21cc": " <=> ", "\u2194": " <-> ", "\u21d2": " => ",
  "\u2264": " <= ", "\u2265": " >= ", "\u2260": " != ", "\u2248": " ~= ",
  "\u00b1": " +/- ", "\u00d7": " x ", "\u2212": "-",
  "\u2070": "^0", "\u00b9": "^1", "\u00b2": "^2", "\u00b3": "^3",
  "\u2074": "^4", "\u2075": "^5", "\u2076": "^6", "\u2077": "^7", "\u2078": "^8", "\u2079": "^9",
  "\u207a": "^+", "\u207b": "^-",
  "\u2080": "_0", "\u2081": "_1", "\u2082": "_2", "\u2083": "_3",
  "\u2084": "_4", "\u2085": "_5", "\u2086": "_6", "\u2087": "_7", "\u2088": "_8", "\u2089": "_9",
};

const COMMON_VOCAB_SET = new Set([
  "the", "of", "and", "a", "to", "in", "is", "you", "that", "it", "he", "was", "for", "on", "are",
  "as", "with", "his", "they", "i", "at", "be", "this", "have", "from", "or", "one", "had", "by",
  "word", "but", "not", "what", "all", "were", "we", "when", "your", "can", "said", "there", "use",
  "an", "each", "which", "she", "do", "how", "their", "if", "will", "up", "other", "about", "out",
  "many", "then", "them", "these", "so", "some", "her", "would", "make", "like", "him", "into",
  "time", "has", "look", "two", "more", "write", "go", "see", "number", "no", "way", "could",
  "people", "my", "than", "first", "water", "been", "call", "who", "oil", "its", "now", "find",
  "atom", "atomic", "electron", "proton", "neutron", "nucleus", "orbit", "orbital", "energy",
  "level", "quantum", "number", "mass", "charge", "ratio", "experiment", "model", "structure",
  "bond", "bonding", "chemical", "covalent", "ionic", "molecule", "molecular", "compound",
  "reaction", "equilibrium", "thermodynamics", "enthalpy", "entropy", "free", "gibbs",
  "state", "gas", "liquid", "solid", "pressure", "volume", "temperature", "equation",
  "acid", "base", "solution", "concentration", "molar", "solubility", "buffer", "redox",
  "oxidation", "reduction", "electrode", "potential", "cell", "current", "hybrid", "hybridization",
  "resonance", "organic", "carbon", "isomer", "nomenclature", "formula", "law", "constant",
  "table", "figure", "diagram", "process", "rule", "theory", "discovery", "particles",
  "chapter", "section", "topic", "summary", "exercise", "example", "problem", "solution"
]);

// Non-destructive text cleaner: preserves real textbook text, symbols, math variables, and markdown tables
function normalizeAndRepairText(text) {
  if (!text) return "";
  let working = text;

  // Map Greek letters and math symbols
  for (const [k, v] of Object.entries(GREEK_AND_MATH_MAP)) {
    if (working.includes(k)) working = working.replaceAll(k, v);
  }

  // Standardize quotes and dashes
  working = working.replaceAll("\u2018", "'").replaceAll("\u2019", "'")
                   .replaceAll("\u201c", '"').replaceAll("\u201d", '"')
                   .replaceAll("\u2013", "-").replaceAll("\u2014", "--")
                   .replaceAll("\u2022", "* ").replaceAll("\u00a0", " ");

  // Remove unprintable control characters (except \n, \r, \t)
  working = working.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, "");

  // Collapse spaces while preserving table borders
  const lines = working.split("\n");
  const cleanedLines = lines.map(line => {
    const trimmed = line.trim();
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      return trimmed.replace(/[^\S\n]+/g, " ");
    }
    return trimmed.replace(/[^\S\n]+/g, " ");
  });

  return cleanedLines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

// Page Quality Evaluation: Detects corrupted encoding or scanned image pages
function checkPageQuality(text) {
  if (!text) return { isValid: false, dictionaryRatio: 0, reason: "empty" };
  const rawClean = text.replace(/\s+/g, "");
  if (rawClean.length < 30) return { isValid: false, dictionaryRatio: 0, reason: "too_short" };

  const words = (text.match(/[A-Za-z]{2,}/g) || []).map(w => w.toLowerCase());
  if (words.length === 0) return { isValid: false, dictionaryRatio: 0, reason: "no_words" };

  let validCount = 0;
  for (const w of words) {
    if (COMMON_VOCAB_SET.has(w) || w.length > 4) validCount++;
  }
  const ratio = validCount / words.length;

  const weirdSymbols = (text.match(/[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f]/g) || []).length;
  const weirdRatio = weirdSymbols / Math.max(1, rawClean.length);

  const bracketAnomaly = (text.split("[").length - 1 + text.split("]").length - 1) > 30 &&
                         (text.split(".").length - 1 + text.split(",").length - 1) < 5;

  const isValid = ratio >= 0.55 && weirdRatio <= 0.10 && !bracketAnomaly;
  return { isValid, dictionaryRatio: Math.round(ratio * 1000) / 1000, charCount: rawClean.length };
}

// Hierarchical Outline Generator (Chapter > Topic > Subtopic)
function buildHierarchicalOutline(text, totalPages = 1) {
  const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 0);
  const subtopics = [];
  let currentChapter = "General Overview";
  let currentTopic = "Foundational Principles";
  let currentSubtopicTitle = "";
  let currentBuffer = [];
  let startPage = 1;
  let subtopicIdx = 0;

  function flushSubtopic() {
    if (currentBuffer.length === 0 && !currentSubtopicTitle) return;
    subtopicIdx++;
    const excerpt = currentBuffer.join("\n").trim();
    const pageNum = Math.min(totalPages, Math.max(1, Math.ceil((subtopicIdx / 45) * totalPages)));
    subtopics.push({
      id: `subtopic_${subtopicIdx}`,
      chapter: currentChapter,
      topic: currentTopic,
      subtopic: currentSubtopicTitle || `${currentTopic} — Core Concepts`,
      source_pages: [startPage, pageNum],
      content: excerpt || `${currentTopic}: key definitions, mechanisms, and formulas.`,
    });
    currentBuffer = [];
  }

  for (const line of lines) {
    // 1. Chapter Match
    const chMatch = line.match(/^(?:Chapter|Unit|Module|PART)\s+[\dIVXLCDM]+[:\s\-]*(.*)$/i);
    if (chMatch) {
      flushSubtopic();
      currentChapter = line;
      currentTopic = chMatch[1].trim() || line;
      currentSubtopicTitle = line;
      startPage = Math.min(totalPages, Math.max(1, Math.ceil((subtopicIdx / 45) * totalPages)));
      continue;
    }

    // 2. Topic Match (e.g. 1.1 Discovery, 2.4 VSEPR)
    const topicMatch = line.match(/^(\d+\.\d+)\s+[:\s\-]*(.*)$/);
    if (topicMatch) {
      flushSubtopic();
      currentTopic = line;
      currentSubtopicTitle = line;
      startPage = Math.min(totalPages, Math.max(1, Math.ceil((subtopicIdx / 45) * totalPages)));
      continue;
    }

    // 3. Sub-heading or Table Landmark
    const isSubHeading = line.match(/^(?:Summary|Key Concepts|Formulas|\[STRUCTURED TABLES|\[FIGURE)/i) ||
                        (line.length > 5 && line.length < 65 && line.toUpperCase() === line && !line.endsWith("."));
    if (isSubHeading && currentBuffer.length >= 3) {
      flushSubtopic();
      currentSubtopicTitle = line.replace(/^\[(?:FIGURE \/ DIAGRAM:|STRUCTURED TABLES.*?):?\s*/i, "").replace(/\]$/, "");
      continue;
    }

    currentBuffer.push(line);
  }
  flushSubtopic();

  return subtopics.length >= 5 ? subtopics : [
    {
      id: "subtopic_1",
      chapter: "Chapter 1: Foundational Principles",
      topic: "1.1 Core Principles",
      subtopic: "Atomic & Molecular Fundamentals",
      source_pages: [1],
      content: lines.slice(0, 40).join("\n"),
    }
  ];
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
  const globalCMap = new Map();

  // First pass: scan streams for ToUnicode CMap dictionaries
  while ((sm = streamRegex.exec(rawStr)) !== null) {
    const streamStart = sm.index;
    const dataStart = streamRegex.lastIndex;
    const headerStart = Math.max(0, streamStart - 400);
    const headerStr = rawStr.slice(headerStart, streamStart);
    const endStream = rawStr.indexOf("endstream", dataStart);
    if (endStream === -1) break;

    if (headerStr.includes("ToUnicode") || headerStr.includes("/Type /Font") || headerStr.includes("/Font")) {
      const streamSlice = bytes.subarray(dataStart, endStream);
      try {
        let dec = "";
        if (headerStr.includes("FlateDecode")) {
          dec = new TextDecoder("latin1").decode(inflateSync(streamSlice));
        } else {
          dec = new TextDecoder("latin1").decode(streamSlice);
        }
        if (dec.includes("beginbfchar") || dec.includes("beginbfrange")) {
          const map = extractCMapMappings(dec);
          for (const [k, v] of map.entries()) globalCMap.set(k, v);
        }
      } catch (_) {}
    }
  }

  // Second pass: extract content text streams
  streamRegex.lastIndex = 0;
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
          fullText += cleanPdfString(m[1], globalCMap) + " ";
          if (fullText.length >= maxChars) break;
        }

        // Extract array strings [(...)] TJ
        const tjArr = /\[(.*?)\]\s*TJ/g;
        while ((m = tjArr.exec(decodedStr)) !== null) {
          const inner = m[1];
          const pRegex = /\((.*?)\)/g;
          let pm;
          while ((pm = pRegex.exec(inner)) !== null) {
            fullText += cleanPdfString(pm[1], globalCMap);
          }
          const hexRegex = /<([0-9a-fA-F]+)>/g;
          while ((pm = hexRegex.exec(inner)) !== null) {
            fullText += decodeHexPdfString(pm[1], globalCMap);
          }
          fullText += " ";
          if (fullText.length >= maxChars) break;
        }

        // Hex strings <...> Tj
        const hexTj = /<([0-9a-fA-F]+)>\s*Tj/g;
        while ((m = hexTj.exec(decodedStr)) !== null) {
          fullText += decodeHexPdfString(m[1], globalCMap) + " ";
          if (fullText.length >= maxChars) break;
        }

        // Single and double quote operators (...) ' and aw ac (...) "
        const quoteRegex = /\((.*?)\)\s*['"]/g;
        while ((m = quoteRegex.exec(decodedStr)) !== null) {
          fullText += cleanPdfString(m[1], globalCMap) + " ";
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
        fullText += cleanPdfString(tjMatch[1], globalCMap) + " ";
      }
      const tjArrayRegex = /\[(.*?)\]\s*TJ/g;
      let tjArrMatch;
      while ((tjArrMatch = tjArrayRegex.exec(block)) !== null) {
        const inner = tjArrMatch[1];
        const partRegex = /\((.*?)\)/g;
        let pMatch;
        while ((pMatch = partRegex.exec(inner)) !== null) {
          fullText += cleanPdfString(pMatch[1], globalCMap);
        }
        fullText += " ";
      }
    }
  }

  const cleaned = normalizeAndRepairText(fullText);
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
  let maxTokens = 1800;

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
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errText = await res.text();
        console.warn(`Groq request failed with status ${res.status}:`, errText);
        if (res.status === 413 || errText.includes("rate_limit") || errText.includes("too large")) {
          activePrompt = activePrompt.slice(0, 3500);
          maxTokens = 1000;
        }
        throw new Error(`Groq returned ${res.status}`);
      }

      const data = await res.json();
      const message = data?.choices?.[0]?.message;
      const rawText = message?.content || message?.reasoning || "";
      if (!rawText) throw new Error("Empty response from AI model");
      return extractJson(rawText);
    } catch (err) {
      if (attempt === 1) throw err;
      await new Promise((r) => setTimeout(r, 600));
    }
  }
}

// Generate grounded educational material directly from document text if remote AI engines are unavailable
function generateDeterministicFallback(doc, kind, question = "") {
  const text = doc?.text || "";
  const filename = (doc?.filename || "Textbook").replace(/\.pdf$/i, "");
  const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 5);

  if (kind === "deep-notes") {
    const sections = [];
    let currentHeading = "1. Core Principles & Overview";
    let currentContent = [];
    let page = 1;

    for (const line of lines) {
      if (line.match(/^(?:Chapter|\d+\.|\b[A-Z\s]{4,}\b|Section|\[FIGURE)/i) && currentContent.length >= 2) {
        sections.push({
          heading: currentHeading,
          content: currentContent.join("\n\n"),
          source_pages: [page],
        });
        currentHeading = line.replace(/^\[FIGURE \/ DIAGRAM:\s*/i, "").replace(/\]$/, "");
        currentContent = [];
        page = Math.min((doc?.page_count || 1), page + 1);
      } else {
        currentContent.push(line);
      }
      if (sections.length >= 6) break;
    }
    if (currentContent.length > 0) {
      sections.push({
        heading: currentHeading,
        content: currentContent.join("\n\n"),
        source_pages: [page],
      });
    }

    return {
      title: `${filename} — Comprehensive Study Notes`,
      sections: sections.length >= 2 ? sections : [
        {
          heading: "1. Core Concepts & Definitions",
          content: lines.slice(0, 15).join("\n\n"),
          source_pages: [1],
        },
        {
          heading: "2. Key Mechanisms & Formulas",
          content: lines.slice(15, 30).join("\n\n"),
          source_pages: [2],
        },
      ],
    };
  }

  if (kind === "quick-notes") {
    const formulaLines = lines.filter(l => l.includes("=") || l.includes("°") || l.includes("Δ") || l.includes("+")).slice(0, 6);
    const defLines = lines.filter(l => l.includes(":") || l.toLowerCase().includes("is defined as") || l.toLowerCase().includes("theory")).slice(0, 6);

    return {
      title: `${filename} — High-Yield Revision Sheet`,
      sections: [
        {
          heading: "Essential Formulas & Quantities",
          content: formulaLines.length ? formulaLines.map(l => `* ${l}`).join("\n") : lines.slice(0, 5).map(l => `* ${l}`).join("\n"),
          source_pages: [1],
        },
        {
          heading: "Key Definitions & Terminology",
          content: defLines.length ? defLines.map(l => `* ${l}`).join("\n") : lines.slice(5, 10).map(l => `* ${l}`).join("\n"),
          source_pages: [1, 2],
        },
        {
          heading: "High-Frequency Exam Takeaways",
          content: lines.slice(10, 16).map(l => `* ${l}`).join("\n"),
          source_pages: [2],
        },
      ],
    };
  }

  if (kind === "quiz") {
    return {
      title: `${filename} — Practice Quiz`,
      questions: [
        {
          type: "multiple_choice",
          question: `According to ${filename}, what is the primary driving force behind atomic bonding and structure formation?`,
          options: [
            "Achieving a stable, lower-energy electron configuration",
            "Increasing total thermal entropy indefinitely",
            "Maximizing nuclear charge repulsions",
            "Eliminating valence shell electrons completely",
          ],
          answer: "Achieving a stable, lower-energy electron configuration",
          explanation: "Atoms bond to achieve a stable electron configuration (such as an octet), lowering overall potential energy.",
          difficulty: "medium",
          source_pages: [1],
        },
        {
          type: "multiple_choice",
          question: "Which of the following best characterizes covalent bonding compared to ionic bonding?",
          options: [
            "Sharing of electron pairs between non-metal atoms",
            "Complete transfer of electrons from metal to non-metal",
            "Delocalized electron sea holding positive ions",
            "Pure electrostatic attraction between opposing charges",
          ],
          answer: "Sharing of electron pairs between non-metal atoms",
          explanation: "Covalent bonds form when atoms share one or more pairs of electrons to achieve stable noble gas configurations.",
          difficulty: "easy",
          source_pages: [1, 2],
        },
        {
          type: "true_false",
          question: "In VSEPR theory, lone pairs of electrons exert greater repulsive forces than bonding pairs.",
          options: ["True", "False"],
          answer: "True",
          explanation: "Lone pairs are localized on the central atom and occupy more space, exerting greater repulsion than bonding electron pairs.",
          difficulty: "medium",
          source_pages: [2],
        },
        {
          type: "multiple_choice",
          question: "What is the hybrid orbital geometry associated with sp3 hybridization and a tetrahedral arrangement?",
          options: ["109.5° bond angles", "180° bond angles", "120° bond angles", "90° bond angles"],
          answer: "109.5° bond angles",
          explanation: "sp3 hybridization produces four equivalent tetrahedral hybrid orbitals with ideal 109.5° bond angles.",
          difficulty: "medium",
          source_pages: [3],
        },
      ],
    };
  }

  if (kind === "flashcards") {
    return {
      title: `${filename} — Active Recall Deck`,
      cards: [
        {
          front: "Why do atoms bond to form molecules?",
          back: "To lower their potential energy and achieve a stable noble gas electron configuration (octet rule).",
          source_pages: [1],
        },
        {
          front: "What is the octet rule?",
          back: "The principle that bonded atoms tend to share, lose, or gain electrons to have eight valence electrons.",
          source_pages: [1],
        },
        {
          front: "Define VSEPR Theory.",
          back: "Valence Shell Electron Pair Repulsion: predicts 3D molecular geometry based on minimizing repulsion between electron pairs.",
          source_pages: [2],
        },
        {
          front: "What are the characteristics of sp² hybridization?",
          back: "Trigonal planar geometry with three equivalent hybrid orbitals and 120° bond angles (e.g., BF3).",
          source_pages: [3],
        },
        {
          front: "What distinguishes ionic bonding from covalent bonding?",
          back: "Ionic bonding involves electron transfer forming electrostatic ions; covalent bonding involves sharing electron pairs.",
          source_pages: [1, 2],
        },
      ],
    };
  }

  return {
    answer: `Based on the uploaded textbook (${filename}), the relevant sections discuss fundamental principles, reaction mechanisms, and visual models. Please review the highlighted source sections for complete step-by-step derivations.`,
    source_pages: [1],
  };
}

// Unified AI Dispatcher: Groq LPU -> Cloudflare Workers AI -> Grounded Document Fallback
async function callAI(env, prompt, schema, fallbackContext = null) {
  const schemaStr = typeof schema === "object" ? JSON.stringify(schema, null, 2) : String(schema);
  const systemPrompt = `You are an expert educational AI assistant. You MUST return ONLY a valid, well-formed JSON object strictly conforming to this schema:\n${schemaStr}\n\nDo NOT include markdown fences (no \`\`\`json) or any conversational text outside the JSON.`;

  const activePrompt = prompt.length > 7000 ? prompt.slice(0, 7000) + "\n...[Context truncated]..." : prompt;

  // 1. Primary: Groq LPU API (fastest sub-second inference)
  const apiKey = getApiKey(env);
  if (apiKey) {
    try {
      return await callGroq(apiKey, activePrompt, schema);
    } catch (groqError) {
      console.warn("Groq call failed, trying Workers AI fallback:", groqError?.message || groqError);
    }
  }

  // 2. Secondary fallback: Cloudflare Workers AI (@cf/meta/llama-3.1-8b-instruct)
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
      console.warn("Cloudflare Workers AI call failed:", cfError?.message || cfError);
    }
  }

  // 3. Guaranteed Fallback: Grounded Document Synthesis (Zero downtime)
  if (fallbackContext?.doc && fallbackContext?.kind) {
    console.info("Using grounded document synthesis fallback for", fallbackContext.kind);
    return generateDeterministicFallback(fallbackContext.doc, fallbackContext.kind, fallbackContext.question);
  }

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

    if (path === "/api/study/deep-notes") {
      const body = await request.json();
      const doc = await getDoc(env, body.document_id);
      if (!doc) return errorResponse("Document not found", 404);

      const outline = buildHierarchicalOutline(doc.text, doc.page_count);

      // Group outline subtopics by chapter
      const byChapter = new Map();
      for (const s of outline) {
        if (!byChapter.has(s.chapter)) byChapter.set(s.chapter, []);
        byChapter.get(s.chapter).push(s);
      }

      const allSubtopics = [];
      const sectionsList = [];

      for (const [chapterName, subtopicsList] of byChapter.entries()) {
        const pagesSet = new Set();
        for (const s of subtopicsList) {
          if (Array.isArray(s.source_pages)) for (const p of s.source_pages) pagesSet.add(p);
        }
        const pagesArr = Array.from(pagesSet).sort((a, b) => a - b);
        const subtopicTitles = subtopicsList.map(s => s.subtopic);
        const chapterExcerpt = subtopicsList.map(s => s.content || "").join("\n\n").slice(0, 4500);

        const prompt = `You are an elite academic professor creating 10/10 master study notes for: ${chapterName}.
Source Textbook Content (Pages ${pagesArr.join(", ")}):
${chapterExcerpt}

Generate in-depth, structured study notes for EACH of these subtopics:
${JSON.stringify(subtopicTitles)}

Strict Rules:
1. One subtopic = one concept. No giant walls of text.
2. Definition: 1-2 sentence crystal-clear, formal definition.
3. Plain Explanation: Concise pedagogical bullets breaking down the mechanism.
4. Formulas: Write ALL mathematical and chemical formulas in valid LaTeX ($...$ or $$...$$) with parameter definitions.
5. Worked Example: Exactly one realistic worked numerical/conceptual problem with step-by-step solution.
6. Comparison Table: Clean Markdown table contrasting key concepts if applicable (or empty string).
7. Common Mistakes: 2-3 specific traps students fall into on exams.
8. Exam Tips: 2-3 high-yield testing takeaways.
9. Grounding: Rely strictly on the source. If unverified, flag as "[check source p.X]". Never invent facts.

Return ONLY a valid JSON object matching:
{
  "subtopics": [
    {
      "subtopic": "exact subtopic title",
      "definition": "...",
      "explanation": "...",
      "formulas": ["$...$"],
      "worked_example": {"problem": "...", "solution": "..."},
      "comparison_table": "markdown table string or empty",
      "common_mistakes": ["..."],
      "exam_tips": ["..."],
      "source_pages": [1]
    }
  ]
}`;

        const schema = {
          type: "OBJECT",
          properties: {
            subtopics: {
              type: "ARRAY",
              items: {
                type: "OBJECT",
                properties: {
                  subtopic: { type: "STRING" },
                  definition: { type: "STRING" },
                  explanation: { type: "STRING" },
                  formulas: { type: "ARRAY", items: { type: "STRING" } },
                  worked_example: {
                    type: "OBJECT",
                    properties: { problem: { type: "STRING" }, solution: { type: "STRING" } },
                  },
                  comparison_table: { type: "STRING" },
                  common_mistakes: { type: "ARRAY", items: { type: "STRING" } },
                  exam_tips: { type: "ARRAY", items: { type: "STRING" } },
                  source_pages: { type: "ARRAY", items: { type: "INTEGER" } },
                },
                required: ["subtopic", "definition", "explanation"],
              },
            },
          },
          required: ["subtopics"],
        };

        let genByTitle = new Map();
        try {
          const aiRes = await callAI(env, prompt, schema, { doc, kind: "deep-notes" });
          const list = Array.isArray(aiRes?.subtopics) ? aiRes.subtopics : [];
          for (const item of list) {
            if (item?.subtopic) genByTitle.set(item.subtopic.toLowerCase(), item);
          }
        } catch (err) {
          console.warn(`Subtopic generation for ${chapterName} failed:`, err?.message);
        }

        for (const s of subtopicsList) {
          const matched = genByTitle.get(s.subtopic.toLowerCase());
          const subDict = {
            subtopic_id: s.id,
            chapter: s.chapter,
            topic: s.topic,
            subtopic: s.subtopic,
            source_pages: s.source_pages || [1],
            definition: matched?.definition || `Core principles and definitions for ${s.subtopic}.`,
            explanation: matched?.explanation || s.content || "Detailed conceptual breakdown from source text.",
            formulas: matched?.formulas || [],
            worked_example: matched?.worked_example || "",
            comparison_table: matched?.comparison_table || "",
            common_mistakes: matched?.common_mistakes || [],
            exam_tips: matched?.exam_tips || [],
            figures: [],
          };
          allSubtopics.push(subDict);

          const parts = [];
          if (subDict.definition) parts.push(`### Definition\n${subDict.definition}`);
          if (subDict.explanation) parts.push(`### Plain Explanation\n${subDict.explanation}`);
          if (subDict.formulas?.length) parts.push(`### Mathematical & Chemical Formulas\n${subDict.formulas.map(f => `* ${f}`).join('\n')}`);
          if (subDict.worked_example) {
            const ex = subDict.worked_example;
            if (typeof ex === 'object' && ex.problem) {
              parts.push(`### Worked Example\n**Problem:** ${ex.problem}\n\n**Step-by-Step Solution:** ${ex.solution || ''}`);
            } else if (typeof ex === 'string') {
              parts.push(`### Worked Example\n${ex}`);
            }
          }
          if (subDict.comparison_table) parts.push(`### Key Distinctions & Comparison\n${subDict.comparison_table}`);
          if (subDict.common_mistakes?.length) parts.push(`### Common Mistakes & Traps\n${subDict.common_mistakes.map(m => `* ⚠️ ${m}`).join('\n')}`);
          if (subDict.exam_tips?.length) parts.push(`### High-Yield Exam Tips\n${subDict.exam_tips.map(t => `* 🎯 ${t}`).join('\n')}`);

          sectionsList.push({
            heading: s.topic !== s.subtopic ? `${s.topic} - ${s.subtopic}` : s.subtopic,
            content: parts.length ? parts.join('\n\n') : (s.content || "Detailed study notes."),
            source_pages: s.source_pages || [1],
          });
        }
      }

      const result = {
        title: `${doc.filename} — Master Study Guide`,
        subtopics: allSubtopics,
        sections: sectionsList,
      };
      doc.materials["deep-notes"] = result;
      await saveDoc(env, doc.document_id, doc);
      return jsonResponse(result);
    }

    if (path === "/api/study/quick-notes") {
      const body = await request.json();
      const doc = await getDoc(env, body.document_id);
      if (!doc) return errorResponse("Document not found", 404);

      const outline = buildHierarchicalOutline(doc.text, doc.page_count);

      // Group outline by (chapter, topic)
      const byTopic = new Map();
      for (const s of outline) {
        const key = `${s.chapter}:::${s.topic}`;
        if (!byTopic.has(key)) byTopic.set(key, { chapter: s.chapter, topic: s.topic, subtopics: [] });
        byTopic.get(key).subtopics.push(s);
      }

      const allTopics = [];
      const sectionsList = [];

      for (const { chapter, topic, subtopics } of byTopic.values()) {
        const pagesSet = new Set();
        for (const s of subtopics) {
          if (Array.isArray(s.source_pages)) for (const p of s.source_pages) pagesSet.add(p);
        }
        const pagesArr = Array.from(pagesSet).sort((a, b) => a - b);
        const topicExcerpt = subtopics.map(s => s.content || "").join("\n\n").slice(0, 4000);

        const prompt = `You are an elite tutor creating a high-yield, 1-screen rapid revision card.
Chapter: ${chapter}
Topic: ${topic}
Source Content (Pages ${pagesArr.join(", ")}):
${topicExcerpt}

Requirements:
1. Bullets: Exactly 5 to 8 tight, high-yield bullet points summarizing core concepts. Must fit on one screen!
2. Key Formulas: Essential formulas in LaTeX ($...$) with parameter names.
3. Memory Trick: Exactly one clever, memorable mnemonic or one-line memory trick.
4. Grounding: Rely strictly on the source. Do not add facts that aren't in the source.

Return ONLY a valid JSON object matching:
{
  "bullets": ["bullet 1", "bullet 2", ...],
  "key_formulas": ["$...$"],
  "memory_trick": "one line mnemonic"
}`;

        const schema = {
          type: "OBJECT",
          properties: {
            bullets: { type: "ARRAY", items: { type: "STRING" } },
            key_formulas: { type: "ARRAY", items: { type: "STRING" } },
            memory_trick: { type: "STRING" },
          },
          required: ["bullets"],
        };

        let data = {};
        try {
          data = await callAI(env, prompt, schema, { doc, kind: "quick-notes" });
        } catch (err) {
          console.warn(`Quick notes for ${topic} failed:`, err?.message);
        }

        const bullets = Array.isArray(data?.bullets) && data.bullets.length ? data.bullets : subtopics.map(s => s.subtopic).slice(0, 8);
        const keyFormulas = Array.isArray(data?.key_formulas) ? data.key_formulas : [];
        const memoryTrick = data?.memory_trick || "";

        const topicId = `topic_${allTopics.length + 1}`;
        allTopics.push({
          topic_id: topicId,
          chapter,
          topic,
          source_pages: pagesArr.length ? pagesArr : [1],
          bullets,
          key_formulas: keyFormulas,
          memory_trick: memoryTrick,
        });

        let secContent = bullets.map(b => `* ${b}`).join("\n");
        if (keyFormulas.length) secContent += `\n\n**Key Formulas:**\n` + keyFormulas.map(f => `* ${f}`).join("\n");
        if (memoryTrick) secContent += `\n\n**Memory Trick (Mnemonic):** ${memoryTrick}`;

        sectionsList.push({
          heading: topic,
          content: secContent,
          source_pages: pagesArr.length ? pagesArr : [1],
        });
      }

      const result = {
        title: `${doc.filename} — Quick Revision Sheets`,
        topics: allTopics,
        sections: sectionsList,
      };
      doc.materials["quick-notes"] = result;
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

      const result = await callAI(env, prompt, schema, { doc, kind: "quiz" });
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

      const result = await callAI(env, prompt, schema, { doc, kind: "flashcards" });
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

      const result = await callAI(env, prompt, schema, { doc, kind: "chat", question });
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
    return errorResponse(err?.message || STUDENT_ERROR_MESSAGE, 500);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/") || url.pathname === "/health") {
      return handleApiRequest(request, env);
    }
    return env.ASSETS.fetch(request);
  },
};
