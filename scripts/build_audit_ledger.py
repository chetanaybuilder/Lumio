import subprocess
import os
from pathlib import Path

# Run git ls-files
res = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
files = [f.strip() for f in res.stdout.strip().splitlines() if f.strip()]

descriptions = {
    ".gitignore": "Specifies intentionally untracked files, dependencies, build artifacts, and caches for git",
    "backend/app/ai/client.py": "Initializes and provides the Google Gemini AI generative client and model configurations",
    "backend/app/ai/prompts/drill.v1.md": "System prompt template for generating targeted mistake remediation micro-drills",
    "backend/app/ai/prompts/evaluate.v1.md": "System prompt template for rubric-based grading and step-by-step student answer evaluation",
    "backend/app/ai/prompts/flashcards.v1.md": "System prompt template for generating active-recall flashcard pairs from textbook concepts",
    "backend/app/ai/prompts/notes.v1.md": "System prompt template for synthesizing structured deep study notes with KaTeX equations",
    "backend/app/ai/prompts/quiz.v1.md": "System prompt template for creating multi-format practice quizzes with answer keys",
    "backend/app/ai/prompts/tutor.v1.md": "System prompt template defining the 5-stage Socratic CBSE tutor with Indian pedagogical analogies",
    "backend/app/ai/retrieval.py": "Implements hybrid retrieval fusing pgvector cosine similarity and tsvector full-text search with RRF",
    "backend/app/ai/schemas.py": "Pydantic response models validating structured AI outputs for notes, flashcards, and quizzes",
    "backend/app/ai/validator.py": "Validates generated markdown for LaTeX math correctness and citation grounding",
    "backend/app/auth/cookies.py": "Sets and clears HttpOnly access, refresh, and JavaScript-readable CSRF security cookies",
    "backend/app/auth/csrf.py": "Implements double-submit cookie CSRF validation for state-modifying HTTP requests",
    "backend/app/auth/google.py": "Validates Google OAuth 2.0 ID tokens against Google Client ID and extracts verified claims",
    "backend/app/auth/jwt.py": "Generates, verifies, and hashes HS256 JWT access tokens, refresh tokens, and CSRF tokens",
    "backend/app/auth/router.py": "Exposes /auth endpoints for Google login, refresh token rotation, logout, and test sessions",
    "backend/app/config.py": "Central Pydantic application settings loading environment variables for DB, AI, R2, and auth",
    "backend/app/db/engine.py": "Configures SQLAlchemy async engine, sessionmaker, NullPool for Neon, and connection retry",
    "backend/app/db/models.py": "SQLAlchemy ORM models defining users, sessions, documents, chunks, syllabus, and study artifacts",
    "backend/app/deps.py": "FastAPI dependency injections resolving current authenticated user from HttpOnly JWT cookies",
    "backend/app/errors.py": "Structured HTTP and AI error handlers formatting standard JSON responses across the API",
    "backend/app/features/cheatsheet.py": "API router generating condensed high-yield formula sheets and definition lists",
    "backend/app/features/coverage.py": "API router calculating syllabus topic coverage metrics for uploaded student documents",
    "backend/app/features/evaluate.py": "API router evaluating student exam answers against official CBSE marking schemes",
    "backend/app/features/flashcards.py": "API router managing flashcard deck generation, review queues, and SM-2 interval scheduling",
    "backend/app/features/mistakes.py": "API router logging student mistakes and generating targeted concept micro-drills",
    "backend/app/features/notes.py": "API router triggering deep study note generation grounded in document chunks",
    "backend/app/features/paper.py": "API router assembling 80-mark blueprint-compliant CBSE sample mock papers across sections A-E",
    "backend/app/features/roadmap.py": "API router calculating personalized topic revision schedules based on mastery and exam dates",
    "backend/app/features/tutor.py": "API router orchestrating multi-turn Socratic tutoring with 5-stage hint escalation",
    "backend/app/ingestion/chunk.py": "Partitions normalized textbook text into semantically coherent, page-mapped context chunks",
    "backend/app/ingestion/clean.py": "Cleans raw extracted PDF text, normalizes whitespace, and preserves math symbols",
    "backend/app/ingestion/embed.py": "Generates 768-dimensional text embeddings using Google gemini-embedding-001",
    "backend/app/ingestion/extract.py": "Extracts text, structural headings, and formulas from PDF pages using PyMuPDF",
    "backend/app/ingestion/mathfix.py": "Heuristically identifies and fixes broken LaTeX mathematical notations in extracted text",
    "backend/app/ingestion/pipeline.py": "End-to-end ingestion pipeline coordinating extraction, chunking, embedding, and DB insertion",
    "backend/app/ingestion/queue.py": "Database-backed asynchronous task queue for managing document ingestion jobs and retries",
    "backend/app/ingestion/worker.py": "Background worker process claiming and executing queued document processing jobs",
    "backend/app/logging.py": "Configures JSON-structured logging and request correlation ID middleware",
    "backend/app/main.py": "FastAPI application entrypoint configuring CORS, security headers, routers, and lifecycle events",
    "backend/app/math/katex.js": "Node/JS KaTeX rendering engine support file for server-side equation validation",
    "backend/app/math/katex.min.js": "Minified KaTeX library script used by server-side math validation sub-processes",
    "backend/app/math/mhchem.js": "KaTeX mhchem extension script for chemical formula parsing and validation",
    "backend/app/math/mhchem.min.js": "Minified KaTeX mhchem chemical equation extension",
    "backend/app/math/validator.py": "Executes headless KaTeX validation on mathematical expressions to detect rendering errors",
    "backend/app/uploads/r2.py": "Client wrapper for Cloudflare R2 S3-compatible multi-part chunked document uploads",
    "backend/app/uploads/router.py": "API router handling multi-part upload initialization, completion, and document metadata",
    "backend/app/uploads/service.py": "Business logic service coordinating R2 presigned URLs and database document records",
    "backend/migrations/versions/0001_init.sql": "PostgreSQL DDL migration creating tables, pgvector HNSW indexes, triggers, and constraints",
    "backend/requirements.in": "Top-level unpinned Python dependencies for FastAPI, SQLAlchemy, asyncpg, and PyMuPDF",
    "backend/seed/blueprints/cbse_10_maths_80m.json": "Official CBSE Class 10 Mathematics 80-mark blueprint specification across Sections A-E",
    "backend/seed/blueprints/cbse_12_maths_80m.json": "Official CBSE Class 12 Mathematics 80-mark blueprint specification across Sections A-E",
    "backend/seed/blueprints/cbse_12_physics_70m.json": "Official CBSE Class 12 Physics 70-mark blueprint specification across Sections A-E",
    "backend/seed/sources.md": "Documentation of official NCERT and CBSE sample paper source URLs used for syllabus seeds",
    "backend/seed/syllabus/cbse_10_maths.json": "Complete official CBSE Class 10 Mathematics syllabus hierarchy with chapter marks",
    "backend/seed/syllabus/cbse_12_maths.json": "Complete official CBSE Class 12 Mathematics syllabus hierarchy with chapter marks",
    "backend/seed/syllabus/cbse_12_physics.json": "Complete official CBSE Class 12 Physics syllabus hierarchy with chapter marks",
    "backend/tests/__init__.py": "Test package initializer for pytest discovery",
    "backend/tests/integration/test_auth_and_api.py": "Integration tests validating health check, cookie issuance, token rotation, CSRF, and logout",
    "backend/tests/unit/test_chunking.py": "Unit tests verifying semantic PDF text chunking boundaries and page-number accuracy",
    "backend/tests/unit/test_cleaning.py": "Unit tests verifying text normalization, ligatures, and mathematical whitespace cleanup",
    "backend/tests/unit/test_invariants.py": "Unit tests asserting system security invariants and role isolation",
    "backend/tests/unit/test_math_validator.py": "Unit tests ensuring KaTeX math validator catches malformed LaTeX syntax",
    "backend/tests/unit/test_roadmap.py": "Unit tests validating revision date scheduling math, past dates, and short deadlines",
    "backend/tests/unit/test_sm2.py": "Unit tests validating the SuperMemo-2 spaced-repetition calculation formulas and bounds",
    "fixtures/fixture_test.pdf": "Binary synthetic test PDF fixture for ingestion and parser verification",
    "fixtures/math_corpus.json": "Test dataset of LaTeX math and chemical formulas used to validate parser reliability",
    "frontend/index.html": "Single-page application HTML entrypoint with Google Identity Services and KaTeX fonts",
    "frontend/package.json": "Frontend NPM package configuration with React 18, Vite, TailwindCSS, and KaTeX",
    "frontend/postcss.config.js": "PostCSS configuration registering TailwindCSS and Autoprefixer plugins",
    "frontend/src/App.jsx": "Root React component providing AuthContext, Layout, and lazy-loaded route definitions",
    "frontend/src/components/Navbar.jsx": "Top navigation header showing brand, user profile, active breadcrumbs, and logout button",
    "frontend/src/components/Sidebar.jsx": "Collapsible sidebar menu for switching between Vault, Notes, Flashcards, and Mocks",
    "frontend/src/components/StatusBadge.jsx": "UI badge component rendering color-coded document and job processing statuses",
    "frontend/src/lib/api.js": "Client HTTP fetch wrapper with automatic CSRF injection and 401 refresh token interceptor",
    "frontend/src/lib/math.jsx": "React component rendering inline and block LaTeX mathematical equations via KaTeX",
    "frontend/src/lib/schemas.js": "Zod client-side schema definitions for validating backend responses",
    "frontend/src/main.jsx": "React application bootstrapping DOM mount with React.StrictMode and BrowserRouter",
    "frontend/src/routes/AttemptView.jsx": "Interactive student exam attempt interface with timer and section navigation",
    "frontend/src/routes/CheatSheetView.jsx": "Cheat sheet view displaying high-yield formulas and key textbook definitions",
    "frontend/src/routes/DocumentView.jsx": "Document details view displaying chunk breakdown and study artifact generation controls",
    "frontend/src/routes/EvaluateView.jsx": "Evaluation review interface showing step-by-step scoring against marking schemes",
    "frontend/src/routes/FlashcardsView.jsx": "Active-recall flashcard study interface with flip animation and SM-2 quality ratings",
    "frontend/src/routes/Landing.jsx": "Public landing page featuring Google Sign-In, demo student login, and feature overview",
    "frontend/src/routes/MistakesView.jsx": "Mistake notebook view tracking student errors and launching concept micro-drills",
    "frontend/src/routes/NotesView.jsx": "Deep study notes reader displaying rendered markdown and KaTeX equations",
    "frontend/src/routes/PaperView.jsx": "Mock paper view rendering official blueprint exam questions with answer schemes",
    "frontend/src/routes/RoadmapView.jsx": "Adaptive revision roadmap view plotting topic mastery against target exam dates",
    "frontend/src/routes/TutorView.jsx": "Socratic CBSE tutor chat interface with hint escalation and document citations",
    "frontend/src/routes/Vault.jsx": "Primary student vault dashboard listing uploaded textbooks, progress, and quick stats",
    "frontend/src/styles.css": "Global Tailwind CSS styles defining glassmorphism tokens, gradients, and scrollbars",
    "frontend/tailwind.config.js": "Tailwind CSS configuration defining dark theme palette, fonts, and animation keyframes",
    "frontend/vite.config.js": "Vite bundler configuration with React plugin, PWA service worker, and dev API proxies",
    "package.json": "Workspace root package configuration defining workspace metadata and KaTeX dependencies",
    "pytest.ini": "Pytest configuration registering asyncio mode, test discovery paths, and warning filters",
    "scripts/generate_seed_data.py": "CLI script generating official syllabus topics and blueprint seeds for Neon Postgres",
    "scripts/make_fixture_pdf.py": "Utility script creating synthetic textbook PDF fixtures containing math formulas"
}

def count_lines(path_str):
    p = Path(path_str)
    if not p.exists():
        return 0
    try:
        content = p.read_bytes()
        # Binary check
        if b'\0' in content[:1024]:
            return len(content)  # Return bytes for binary
        return len(content.splitlines())
    except Exception:
        return 0

ledger_entries = []
for f in files:
    lc = count_lines(f)
    desc = descriptions.get(f, f"Source component for {Path(f).name}")
    is_binary = f.endswith(".pdf") or f.endswith(".png")
    metric = f"{lc} bytes" if is_binary else f"{lc} lines"
    ledger_entries.append((f, metric, desc))

audit_content = ["# VexoVault System Ledger & File Audit\n"]
audit_content.append(f"**Total Tracked Files (`git ls-files`):** {len(files)}\n")
audit_content.append("| File Path | Size / Lines | Purpose & Description |")
audit_content.append("| :--- | :--- | :--- |")

for f, metric, desc in ledger_entries:
    audit_content.append(f"| [`{f}`](file:///{Path(f).resolve().as_posix()}) | {metric} | {desc} |")

audit_text = "\n".join(audit_content) + "\n"

with open("AUDIT.md", "w", encoding="utf-8") as out:
    out.write(audit_text)

print(f"AUDIT.md successfully generated with {len(ledger_entries)} entries.")
