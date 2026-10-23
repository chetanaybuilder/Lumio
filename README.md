<div align="center">

# 🌟 Lumio
### Intelligent, Grounded Textbook Study Workspace Powered by Groq & Cloudflare

[![Live App](https://img.shields.io/badge/Live%20Demo-lumio--study.pages.dev-10b981?style=for-the-badge&logo=cloudflare&logoColor=white)](https://lumio-study.pages.dev)
[![Groq AI](https://img.shields.io/badge/AI-Groq%20LPU%20(Sub--5s)-f55036?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com)
[![Cloudflare](https://img.shields.io/badge/Deployed%20on-Cloudflare%20Pages-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)](https://pages.cloudflare.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://vitejs.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

<br/>

<a href="https://lumio-study.pages.dev">
  <img src="docs/assets/lumio-preview.png" alt="Lumio Study Workspace Preview" width="100%" style="border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.4);" />
</a>

<br/><br/>

**Transform any textbook PDF into structured, sourced study notes, interactive practice quizzes, active-recall flashcards, and an evidence-grounded AI chat with exact page citations in under 5 seconds.**

[🌐 Explore Live Application](https://lumio-study.pages.dev) • [📖 Architecture](ARCHITECTURE.md) • [🚀 Quick Start](#-quick-start) • [⚡ Cloudflare Deployment](#-deployment-to-cloudflare)

---

</div>

## ✨ Key Features

| Feature | Description |
| :--- | :--- |
| **📑 Structured Deep Notes** | Generates section-by-section concept breakdowns, key definitions, formulas, and revision priorities grounded in source pages. |
| **⚡ Quick Revision Notes** | High-density bulleted summaries designed for rapid pre-exam review. |
| **🧪 Interactive Quizzes** | Multiple choice, true/false, and short answer practice problems complete with detailed explanations and difficulty levels. |
| **🗂️ Active Recall Flashcards** | Front-and-back study cards formatted for active recall and spaced repetition. |
| **💬 Ask Lumio (Contextual Q&A)** | Ask questions directly against your textbook. Every answer is strictly grounded in the document and cites exact source pages. |
| **⚡ High-Speed Inference** | Powered by Groq LPUs (`llama-3.3-70b-versatile`), generating high-quality structured study outputs with low latency. |
| **📄 Styled PDF Export** | Download generated notes, quiz sheets, or flashcard decks as beautifully formatted, ready-to-print PDFs. |
| **🔒 Ephemeral & Private** | Zero login required. Each tab receives an isolated, temporary session that self-cleans after inactivity. |

---

## 🏗️ Architecture & Pipeline

```mermaid
graph TD
    A[Textbook PDF Upload] --> B[PyMuPDF Structure-Aware Extractor]
    B --> C[Text Normalization & Heading Detector]
    C --> D[Context Chunker & Heading Mapper]
    D --> E[Semantic Embeddings & BM25 Index]
    E --> F[In-Memory Scoped Hybrid Vector Store]
    
    F --> G[Ask Lumio: Hybrid Retrieval + RRF]
    D --> H[Map-Reduce Study Prompt Assembler]
    
    G --> I[Groq LPU Engine: llama-3.3-70b-versatile]
    H --> I[Groq LPU Engine: llama-3.3-70b-versatile]
    
    I --> J[Type-Safe Pydantic Output Validation]
    J --> K[Source Page Verification Filter]
    K --> L[React Workspace UI]
    K --> M[Styled PDF Generator Engine]
```

### 1. Document Extraction & Chunking
- Ingestion accepts textbooks up to 500 pages and 20 MB.
- Text is extracted with PyMuPDF layout analysis, preserving chemical formulas, math symbols, and tables, partitioned into semantically coherent chunks mapped to exact page numbers.

### 2. Grounded Vector Retrieval
- Text chunks are indexed locally using semantic embeddings and BM25 keyword search, fused with Reciprocal Rank Fusion.
- Hybrid search retrieves nearest-neighbor excerpts with high recall and precision.

### 3. Structured Generation & Page Verification
- Study artifacts (Notes, Quizzes, Flashcards, Chat) are generated using Groq (`llama-3.3-70b-versatile`) with strict JSON schema and Pydantic validation.
- An automated post-processor inspects all citations, verifying claims against actual source pages.

### 4. Production Deployment Architecture
- **Frontend**: Static React + Vite application deployed to **Cloudflare Pages** for fast global CDN distribution.
- **Backend**: FastAPI Python service running on container/VM infrastructure (Fly.io, Render, Railway, or VPS) with access to PyMuPDF and Groq LPUs.
- Communication via `VITE_API_BASE_URL` with CORS configured via `FRONTEND_ORIGINS`.

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 20+** and **npm**
- **Groq API Key** ([Get one for free at console.groq.com](https://console.groq.com/keys))

---

### 1. Clone the Repository
```bash
git clone https://github.com/chetanaybuilder/Lumio.git
cd Lumio
```

### 2. Configure Backend
```bash
cd backend
python -m venv .venv

# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On macOS / Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` and insert your Groq API Key:
```env
GROQ_API_KEY=your_actual_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
SESSION_TTL_SECONDS=3600
MAX_UPLOAD_MB=20
MAX_PDF_PAGES=500
FRONTEND_ORIGINS=http://localhost:5173
```

Start the FastAPI development server:
```bash
uvicorn app.main:app --reload --port 8000
```

### 3. Configure Frontend
In a new terminal window:
```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open your browser to `http://localhost:5173`. The Vite dev server will proxy `/api` calls directly to your local FastAPI backend.

---

## 🧪 Running Automated Tests

Lumio includes comprehensive integration and workflow test suites:

```bash
cd backend
python -m pytest tests/ -v
```

---

## ⚡ Deployment

Lumio is architected for a production topology with separated concerns:
- **Frontend**: Deployed to **Cloudflare Pages** for global edge CDN distribution of static assets.
- **Backend**: Deployed to a container/VM platform (Render, Fly.io, Railway, or VPS) running FastAPI, PyMuPDF, and embedding/retrieval models.

### 1. Deploy Frontend to Cloudflare Pages:
```bash
cd frontend
npm run build
npx wrangler pages deploy dist --project-name lumio-study
```
Set environment variable `VITE_API_BASE_URL` in Cloudflare Pages dashboard to your backend URL (e.g., `https://api.lumio-study.com`).

### 2. Deploy Backend:
Deploy the `backend/` directory using Docker or standard Python ASGI server (`uvicorn app.main:app --host 0.0.0.0 --port 8000`), configuring:
- `GROQ_API_KEY`: Your Groq API key
- `FRONTEND_ORIGINS`: `https://lumio-study.pages.dev` (or custom domain)

---

## 📡 API Reference

All requests must include the `X-Session-Token` header obtained from `POST /api/sessions`.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Application uptime health check |
| `POST` | `/api/sessions` | Create a new anonymous study session |
| `DELETE` | `/api/sessions/current` | Close current session and purge in-memory vectors |
| `POST` | `/api/documents/upload` | Upload a PDF textbook (`multipart/form-data`) |
| `GET` | `/api/documents/{id}` | Retrieve document status and metadata |
| `POST` | `/api/study/deep-notes` | Generate comprehensive section-by-section notes |
| `POST` | `/api/study/quick-notes` | Generate high-density bulleted revision notes |
| `POST` | `/api/study/quiz` | Generate interactive quiz with answer explanations |
| `POST` | `/api/study/flashcards` | Generate front-and-back flashcard deck |
| `POST` | `/api/chat` | Ask Lumio textbook-grounded Q&A with citations |
| `POST` | `/api/export/pdf` | Export generated material as a styled PDF document |

---

## 🛡️ Security & Privacy Principles

1. **No Account Tracking**: Sessions are anonymous and tracked via ephemeral cryptographically secure tokens.
2. **Strict Document Isolation**: Cross-session document access is blocked at the routing layer; sessions cannot read or query documents they do not own.
3. **Prompt Injection Resistance**: All extracted document excerpts are framed in untrusted boundary blocks to prevent indirect prompt injection attacks.
4. **Citation Auditing**: Generation outputs are strictly verified against actual page numbers present in the retrieved textbook excerpts.

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).

<div align="center">
  <sub>Built with ❤️ for students, researchers, and self-learners worldwide.</sub>
</div>
