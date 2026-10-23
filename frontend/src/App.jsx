/**
 * App Component — Lumio Frontend
 * ================================
 *
 * The root React component that orchestrates the entire Lumio study
 * workspace.  It manages:
 *
 * - **Session lifecycle** — automatic creation, restoration from
 *   `sessionStorage`, and explicit reset ("Start fresh").
 * - **PDF upload** — drag-and-drop or file picker, large PDF support,
 *   client-side size validation, sample textbook loader.
 * - **Study tools** — deep notes, quick notes, quiz lab, flashcards,
 *   and Ask Lumio chat, each rendered by a dedicated panel component.
 * - **PDF export** — download any generated material as a styled PDF.
 */

import { useEffect, useRef, useState, useMemo } from 'react'
import katex from 'katex'
import {
  BookOpenText, BrainCircuit, Check, ChevronDown, ChevronLeft, ChevronRight, ChevronUp,
  CircleHelp, Download, FileText, Flame, Layers3, LoaderCircle, Mail, MessageCircle,
  RotateCcw, Search, Send, Shuffle, Sparkles, Trash2, Upload, X,
} from 'lucide-react'
import { closeSession, createSession, exportPdf, generate, getDocument, uploadDocument } from './api.js'


// ---------------------------------------------------------------------------
// Navigation configuration
// ---------------------------------------------------------------------------

/** Study tool definitions used by the sidebar and routing logic. */
const tools = [
  { id: 'deep-notes', label: 'Deep notes', icon: BookOpenText },
  { id: 'quick-notes', label: 'Quick notes', icon: FileText },
  { id: 'quiz', label: 'Quiz lab', icon: CircleHelp },
  { id: 'flashcards', label: 'Flashcards', icon: Layers3 },
  { id: 'chat', label: 'Ask Lumio', icon: MessageCircle },
]

/** Maps tool IDs to their API endpoint paths and material cache keys. */
const materialRoutes = {
  'deep-notes': ['/api/study/deep-notes', 'deep-notes'],
  'quick-notes': ['/api/study/quick-notes', 'quick-notes'],
  quiz: ['/api/study/quiz', 'quiz'],
  flashcards: ['/api/study/flashcards', 'flashcards'],
}


// ═══════════════════════════════════════════════════════════════════════════
// MAIN APP COMPONENT
// ═══════════════════════════════════════════════════════════════════════════

export default function App() {
  // --- Core session and document state ---
  const [token, setToken] = useState('')
  const [document, setDocument] = useState(null)
  const [view, setView] = useState('deep-notes')
  const [materials, setMaterials] = useState({})
  const [loading, setLoading] = useState('Starting your private study space…')
  const [error, setError] = useState('')
  const [isDragging, setIsDragging] = useState(false)

  // --- Chat state ---
  const [chat, setChat] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [busyChat, setBusyChat] = useState(false)

  // --- Quiz state ---
  const [quizAnswers, setQuizAnswers] = useState({})
  const [quizSubmitted, setQuizSubmitted] = useState(false)

  // --- Flashcard state ---
  const [cardIndex, setCardIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)

  // --- DOM refs ---
  const fileInput = useRef(null)
  const chatEnd = useRef(null)

  // -------------------------------------------------------------------------
  // Session initialization — restore from sessionStorage or create new
  // -------------------------------------------------------------------------
  useEffect(() => {
    let alive = true
    const start = async () => {
      const saved = sessionStorage.getItem('lumio-session')
      const savedDocument = sessionStorage.getItem('lumio-document')
      try {
        if (saved) {
          let restoredDocument = null
          if (savedDocument) {
            const cached = JSON.parse(savedDocument)
            restoredDocument = await getDocument(saved, cached.document_id)
          }
          if (alive) {
            setToken(saved)
            if (restoredDocument) setDocument(restoredDocument)
            setLoading('')
          }
          return
        }
      } catch {
        sessionStorage.removeItem('lumio-session')
        sessionStorage.removeItem('lumio-document')
      }
      try {
        const created = await createSession()
        sessionStorage.setItem('lumio-session', created.session_token)
        if (alive) {
          setToken(created.session_token)
          setLoading('')
        }
      } catch (reason) {
        if (alive) {
          setError(reason.message)
          setLoading('')
        }
      }
    }
    start()
    return () => { alive = false }
  }, [])

  // -------------------------------------------------------------------------
  // Auto-scroll chat to the latest message
  // -------------------------------------------------------------------------
  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chat, busyChat])

  // -------------------------------------------------------------------------
  // Session reset — close old session, create new one
  // -------------------------------------------------------------------------
  async function resetSession() {
    setError('')
    try { if (token) await closeSession(token) } catch { /* cleanup is automatic */ }
    sessionStorage.removeItem('lumio-session')
    sessionStorage.removeItem('lumio-document')
    setToken('')
    setDocument(null)
    setMaterials({})
    setChat([])
    setView('deep-notes')
    setLoading('Opening a fresh study space…')
    try {
      const created = await createSession()
      sessionStorage.setItem('lumio-session', created.session_token)
      setToken(created.session_token)
      setLoading('')
    } catch (reason) {
      setLoading('')
      setError(reason.message)
    }
  }

  // -------------------------------------------------------------------------
  // File upload handler (with large PDF support & size validation)
  // -------------------------------------------------------------------------
  async function onFile(file) {
    if (!file || !token) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please select a valid PDF textbook file to continue.')
      return
    }
    if (file.size > 25 * 1024 * 1024) {
      setError('This textbook exceeds the 20 MB size limit. Please choose a specific chapter or document under 20 MB.')
      return
    }

    const sizeMb = (file.size / (1024 * 1024)).toFixed(1)
    setError('')
    setLoading(`Reading "${file.name}" (${sizeMb} MB) and preparing pages…`)

    try {
      const uploaded = await uploadDocument(token, file)
      setDocument(uploaded)
      sessionStorage.setItem('lumio-document', JSON.stringify(uploaded))
      setMaterials({})
      setView('deep-notes')
    } catch (reason) {
      setError(reason.message)
    } finally {
      setLoading('')
    }
  }

  // -------------------------------------------------------------------------
  // Sample textbook loader (instant test)
  // -------------------------------------------------------------------------
  async function loadSampleTextbook() {
    if (!token) return
    setError('')
    setLoading('Loading CBSE Chemistry textbook sample (16 pages)…')
    try {
      const res = await fetch('/Chemistry_Textbook_CBSE.pdf')
      if (!res.ok) throw new Error('Sample textbook not found')
      const blob = await res.blob()
      const sampleFile = new File([blob], 'Chemistry_Textbook_CBSE.pdf', { type: 'application/pdf' })
      await onFile(sampleFile)
    } catch (reason) {
      setError('Could not load sample textbook: ' + reason.message)
      setLoading('')
    }
  }

  // -------------------------------------------------------------------------
  // Study tool activation — generates material on first open
  // -------------------------------------------------------------------------
  async function openTool(id) {
    setView(id)
    setError('')
    if (!document || !materialRoutes[id] || materials[id]) return
    const [path, kind] = materialRoutes[id]
    setLoading(`Building ${tools.find((tool) => tool.id === id)?.label.toLowerCase()} from your textbook…`)
    try {
      const payload = { document_id: document.document_id }
      if (id === 'quiz') payload.count = 8
      const generated = await generate(path, token, payload)
      setMaterials((current) => ({ ...current, [kind]: generated }))
      setQuizAnswers({})
      setQuizSubmitted(false)
      setCardIndex(0)
      setFlipped(false)
    } catch (reason) {
      setError(reason.message)
    } finally {
      setLoading('')
    }
  }

  // -------------------------------------------------------------------------
  // PDF export — download material as a styled PDF
  // -------------------------------------------------------------------------
  async function download(kind) {
    try {
      const blob = await exportPdf(token, document.document_id, kind)
      const link = window.document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `lumio-${kind}.pdf`
      link.click()
      URL.revokeObjectURL(link.href)
    } catch (reason) {
      setError(reason.message)
    }
  }

  // -------------------------------------------------------------------------
  // Chat — send a question to Ask Lumio
  // -------------------------------------------------------------------------
  async function sendQuestion(event, customQuestion = null) {
    if (event) event.preventDefault()
    const question = (customQuestion || chatInput).trim()
    if (!question || busyChat) return
    setChatInput('')
    setChat((current) => [...current, { role: 'student', content: question }])
    setBusyChat(true)
    setError('')
    try {
      const answer = await generate('/api/chat', token, { document_id: document.document_id, question })
      setChat((current) => [...current, { role: 'lumio', ...answer }])
    } catch (reason) {
      setError(reason.message)
    } finally {
      setBusyChat(false)
    }
  }

  // -------------------------------------------------------------------------
  // Derived state
  // -------------------------------------------------------------------------
  const currentTool = tools.find((tool) => tool.id === view) || tools[0]
  const loadingWorkspace = Boolean(loading)

  // ═══════════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════════

  return (
    <div className="app-shell">
      {/* ───────────── SIDEBAR ───────────── */}
      <aside className="sidebar">
        <button className="brand" onClick={() => setView('deep-notes')} aria-label="Lumio home">
          <span className="brand-mark"><Flame size={21} strokeWidth={2.6} /></span>
          <span>Lumio<span className="brand-period">.</span></span>
        </button>

        {/* Document status chip */}
        <div className="side-label">YOUR WORKSPACE</div>
        <div className="document-chip">
          <span className="document-icon"><FileText size={17} /></span>
          <span className="document-meta">
            <strong>{document?.filename || 'No textbook yet'}</strong>
            <small>{document ? `${document.page_count} pages · Ready` : 'Start with a PDF'}</small>
          </span>
          {document && <span className="ready-dot" />}
        </div>

        {/* Study tool navigation */}
        <div className="side-label tools-label">STUDY TOOLS</div>
        <nav className="tool-nav" aria-label="Study tools">
          {tools.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav-item ${view === id ? 'active' : ''}`} onClick={() => openTool(id)} disabled={!document}>
              <Icon size={18} strokeWidth={1.9} /><span>{label}</span>
              {view === id && <span className="active-mark" />}
            </button>
          ))}
        </nav>

        {/* Sidebar footer */}
        <div className="sidebar-bottom">
          <div className="privacy-note">
            <span className="privacy-glyph">✳</span>
            <span><b>Just your study space</b><small>Private, temporary session</small></span>
          </div>
          {document && <button className="new-session" onClick={resetSession}><RotateCcw size={15} /> Start fresh</button>}
          <div className="sidebar-foot">MADE FOR THE NEXT BIG IDEA</div>
        </div>
      </aside>

      {/* ───────────── MAIN CONTENT ───────────── */}
      <main className="main-area">
        {/* Top bar with breadcrumb and actions */}
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span><span className="crumb-slash">/</span><strong>{currentTool.label}</strong>
          </div>
          <div className="top-actions">
            {document && <div className="status-pill"><span /> Textbook ready</div>}
            {document && (
              <button className="icon-button upload-again" title="Start a new study session" onClick={resetSession}>
                <Upload size={17} /><span>New textbook</span>
              </button>
            )}
          </div>
        </header>

        {/* Error banner */}
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button onClick={() => setError('')} aria-label="Dismiss error"><X size={16} /></button>
          </div>
        )}

        {/* ─── Welcome / Upload view ─── */}
        {!document ? (
          <section className="welcome-view">
            <div className="welcome-copy">
              <div className="eyebrow"><span className="eyebrow-line" /> YOUR FOCUS, AMPLIFIED</div>
              <h1>Turn pages into<br /><em>aha</em> moments.</h1>
              <p>Bring a textbook. Leave with structured notes, active recall flashcards, and grounded explanations.</p>
            </div>
            <div
              className={`upload-panel ${isDragging ? 'is-dragging' : ''}`}
              onDragOver={(event) => { event.preventDefault(); setIsDragging(true) }}
              onDragEnter={(event) => { event.preventDefault(); setIsDragging(true) }}
              onDragLeave={(event) => { event.preventDefault(); setIsDragging(false) }}
              onDrop={(event) => {
                event.preventDefault()
                setIsDragging(false)
                if (event.dataTransfer.files?.[0]) onFile(event.dataTransfer.files[0])
              }}
            >
              <div className="upload-art">
                <span className="orbit orbit-one" />
                <span className="orbit orbit-two" />
                <span className="upload-icon"><Upload size={25} /></span>
                <span className="sparkle sparkle-one">✦</span>
                <span className="sparkle sparkle-two">✳</span>
              </div>
              <h2>{isDragging ? 'Release to upload PDF' : 'Drop your textbook here'}</h2>
              <p>PDF only · Up to 20 MB · Up to 500 pages · Fast Edge OCR</p>
              <button className="primary-button" disabled={!token || loadingWorkspace} onClick={() => fileInput.current?.click()}>
                {loadingWorkspace ? <LoaderCircle className="spin" size={17} /> : <Upload size={17} />}
                {loadingWorkspace ? 'Processing textbook…' : 'Choose a PDF'}
              </button>
              <input ref={fileInput} type="file" accept="application/pdf,.pdf" hidden onChange={(event) => onFile(event.target.files[0])} />

              {/* Sample textbook quick-loader */}
              <div className="sample-loader">
                <span className="sample-divider">or explore immediately</span>
                <button
                  type="button"
                  className="sample-badge-btn"
                  onClick={loadSampleTextbook}
                  disabled={!token || loadingWorkspace}
                >
                  <Sparkles size={14} /> Try sample: CBSE Chemistry Textbook (16 pages)
                </button>
              </div>

              {loadingWorkspace && token && (
                <div className="upload-status" role="status" aria-live="polite">
                  <LoaderCircle className="spin" size={15} />{loading}
                </div>
              )}
              <div className="upload-assurance">
                <span>01</span> Private by design <i /> <span>02</span> No account needed <i /> <span>03</span> Groq LPU powered
              </div>
            </div>
            <div className="how-row">
              <span className="how-title">A little less cramming.<br /><b>A lot more clarity.</b></span>
              <div><span className="step-no">01</span><b>Bring your book</b><small>Start with any textbook PDF.</small></div>
              <div><span className="step-no">02</span><b>Pick your rhythm</b><small>Notes, quizzes, cards, or chat.</small></div>
              <div><span className="step-no">03</span><b>Make it stick</b><small>Study with page-cited evidence.</small></div>
            </div>
          </section>

        ) : (
          /* ─── Study workspace view ─── */
          <section className="work-view">
            <div className="page-heading">
              <div>
                <div className="eyebrow"><span className="eyebrow-line" /> STUDY STUDIO</div>
                <h1>
                  {view === 'deep-notes' ? 'Deep notes' :
                   view === 'quick-notes' ? 'Quick notes' :
                   view === 'quiz' ? 'Quiz lab' :
                   view === 'flashcards' ? 'Flashcards' : 'Ask Lumio'}
                </h1>
                <p>{view === 'chat' ? 'A textbook-grounded conversation, page by page.' : `Built from ${document.filename}`}</p>
              </div>
              {materials[view] && view !== 'chat' && (
                <button className="outline-button" onClick={() => download(view)}>
                  <Download size={16} /> Export PDF
                </button>
              )}
            </div>

            {/* Loading indicator */}
            {loadingWorkspace && <div className="loading-row"><LoaderCircle className="spin" size={18} />{loading}</div>}

            {/* Study tool panels */}
            {!loadingWorkspace && view === 'chat' && (
              <ChatPanel
                chat={chat}
                chatInput={chatInput}
                setChatInput={setChatInput}
                onSubmit={sendQuestion}
                onAsk={sendQuestion}
                onClear={() => setChat([])}
                busy={busyChat}
                chatEnd={chatEnd}
              />
            )}
            {!loadingWorkspace && (view === 'deep-notes' || view === 'quick-notes') && (
              <NotesPanel
                material={materials[view]}
                view={view}
                onGenerate={() => openTool(view)}
                actionLabel={`Generate ${view === 'deep-notes' ? 'deep notes' : 'quick notes'}`}
                onCopy={() => navigator.clipboard?.writeText(
                  materials[view]?.sections?.map((item) => `${item.heading}\n${item.content}`).join('\n\n') || ''
                )}
              />
            )}
            {!loadingWorkspace && view === 'quiz' && (
              <QuizPanel
                quiz={materials.quiz}
                answers={quizAnswers}
                setAnswers={setQuizAnswers}
                submitted={quizSubmitted}
                setSubmitted={setQuizSubmitted}
                onGenerate={() => openTool('quiz')}
                onRestart={() => { setQuizAnswers({}); setQuizSubmitted(false) }}
              />
            )}
            {!loadingWorkspace && view === 'flashcards' && (
              <FlashcardPanel
                deck={materials.flashcards}
                index={cardIndex}
                setIndex={setCardIndex}
                flipped={flipped}
                setFlipped={setFlipped}
                onGenerate={() => openTool('flashcards')}
                onShuffle={() => {
                  const cards = [...(materials.flashcards?.cards || [])]
                  for (let i = cards.length - 1; i > 0; i--) {
                    const j = Math.floor(Math.random() * (i + 1));
                    [cards[i], cards[j]] = [cards[j], cards[i]]
                  }
                  setMaterials((current) => ({ ...current, flashcards: { ...current.flashcards, cards } }))
                  setCardIndex(0)
                  setFlipped(false)
                }}
              />
            )}
          </section>
        )}
      </main>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════
// KATEX MATH RENDERING COMPONENT — Inline ($...$) & Block ($$...$$)
// ═══════════════════════════════════════════════════════════════════════════

function MathText({ text }) {
  if (!text || typeof text !== 'string') return null

  // Matches $$...$$ (display math) or $...$ (inline math)
  const mathRegex = /(\$\$[\s\S]*?\$\$|\$[^\$\n]+?\$)/g
  const parts = text.split(mathRegex)

  return (
    <span className="math-text-flow">
      {parts.map((part, index) => {
        if (!part) return null
        if (part.startsWith('$$') && part.endsWith('$$') && part.length >= 4) {
          const rawMath = part.slice(2, -2).trim()
          try {
            const html = katex.renderToString(rawMath, { displayMode: true, throwOnError: false })
            return (
              <span
                key={index}
                className="katex-display-wrapper"
                dangerouslySetInnerHTML={{ __html: html }}
              />
            )
          } catch (_) {
            return <code key={index} className="raw-math-fallback">{part}</code>
          }
        }
        if (part.startsWith('$') && part.endsWith('$') && part.length >= 2) {
          const rawMath = part.slice(1, -1).trim()
          try {
            const html = katex.renderToString(rawMath, { displayMode: false, throwOnError: false })
            return (
              <span
                key={index}
                className="katex-inline-wrapper"
                dangerouslySetInnerHTML={{ __html: html }}
              />
            )
          } catch (_) {
            return <code key={index} className="raw-math-fallback">{part}</code>
          }
        }
        return <span key={index}>{part}</span>
      })}
    </span>
  )
}


// ═══════════════════════════════════════════════════════════════════════════
// FORMATTED CONTENT HELPER — Diagrams, Tables & Lists with KaTeX
// ═══════════════════════════════════════════════════════════════════════════

function FormattedContent({ content }) {
  if (!content) return null

  const blocks = content.split(/\n\n+/)

  return (
    <div className="formatted-content">
      {blocks.map((block, idx) => {
        const trimmed = block.trim()

        // 1. Diagram / Visual callout
        if (trimmed.startsWith('[FIGURE / DIAGRAM:') || trimmed.startsWith('[VISUAL ELEMENTS')) {
          const cleanText = trimmed.replace(/^\[(?:FIGURE \/ DIAGRAM:|VISUAL ELEMENTS DETECTED.*?):?\s*/i, '').replace(/\]$/, '')
          return (
            <div key={idx} className="diagram-callout-card">
              <div className="diagram-callout-header">
                <span className="diagram-callout-icon">🎨</span>
                <span className="diagram-callout-title">Visual & Diagram Analysis</span>
              </div>
              <div className="diagram-callout-body"><MathText text={cleanText} /></div>
            </div>
          )
        }

        // 2. Markdown table
        if (trimmed.includes('| --- |') || (trimmed.startsWith('|') && trimmed.includes('\n|'))) {
          const lines = trimmed.split('\n').filter(l => l.trim().startsWith('|'))
          if (lines.length >= 2) {
            const headerRow = lines[0].split('|').slice(1, -1).map(c => c.trim())
            const dataRows = lines.slice(2).map(l => l.split('|').slice(1, -1).map(c => c.trim()))
            return (
              <div key={idx} className="table-responsive-wrapper">
                <table className="anime-table">
                  <thead>
                    <tr>
                      {headerRow.map((col, i) => <th key={i}><MathText text={col} /></th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {dataRows.map((row, rIdx) => (
                      <tr key={rIdx}>
                        {row.map((cell, cIdx) => <td key={cIdx}><MathText text={cell} /></td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        }

        // 3. Bullet list
        if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
          const items = trimmed.split('\n').filter(l => l.trim().startsWith('* ') || l.trim().startsWith('- '))
          return (
            <ul key={idx} className="formatted-list">
              {items.map((item, i) => (
                <li key={i}><MathText text={item.replace(/^[\*\-]\s+/, '')} /></li>
              ))}
            </ul>
          )
        }

        // 4. Regular paragraph
        return <p key={idx} className="formatted-paragraph"><MathText text={trimmed} /></p>
      })}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════
// SUBTOPIC CARD — Collapsible, Modular 10/10 Atomic Study Concept
// ═══════════════════════════════════════════════════════════════════════════

function SubtopicCard({ sub, index, expanded, onToggle, accent }) {
  const exampleObj = typeof sub.worked_example === 'object' && sub.worked_example !== null
    ? sub.worked_example
    : (sub.worked_example ? { problem: sub.worked_example, solution: '' } : null)

  return (
    <section
      className={`subtopic-card anime-section ${expanded ? 'is-expanded' : 'is-collapsed'}`}
      id={`subtopic-${index}`}
      style={{
        '--anime-border': accent.border,
        '--anime-bg': accent.bg,
        '--anime-glow': accent.glow,
      }}
    >
      {/* Header toggle bar */}
      <div
        className="subtopic-card-header"
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onToggle() }}
      >
        <div className="subtopic-header-left">
          <span className="subtopic-number" style={{ background: accent.border }}>
            {String(index + 1).padStart(2, '0')}
          </span>
          <div className="subtopic-title-group">
            <span className="subtopic-breadcrumb">
              {sub.chapter} {sub.topic && sub.topic !== sub.chapter ? `· ${sub.topic}` : ''}
            </span>
            <h3 className="subtopic-title">{sub.subtopic}</h3>
          </div>
        </div>

        <div className="subtopic-header-right">
          {sub.source_pages?.length > 0 && (
            <span className="subtopic-page-badge" title="Source textbook page numbers">
              📖 p.{sub.source_pages.join(', ')}
            </span>
          )}
          <span className="subtopic-toggle-btn" aria-label={expanded ? 'Collapse section' : 'Expand section'}>
            {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </span>
        </div>
      </div>

      {/* Collapsible card body */}
      {expanded && (
        <div className="subtopic-card-body">
          {/* 1. Formal Definition */}
          {sub.definition && (
            <div className="subtopic-box subtopic-def-box">
              <div className="subtopic-box-label">📌 FORMAL DEFINITION</div>
              <div className="subtopic-box-content">
                <MathText text={sub.definition} />
              </div>
            </div>
          )}

          {/* 2. Plain Pedagogical Explanation */}
          {sub.explanation && (
            <div className="subtopic-box subtopic-exp-box">
              <div className="subtopic-box-label">📝 CORE CONCEPT EXPLANATION</div>
              <FormattedContent content={sub.explanation} />
            </div>
          )}

          {/* 3. Formulas & Equations (with KaTeX) */}
          {sub.formulas && sub.formulas.length > 0 && (
            <div className="subtopic-box subtopic-formula-box">
              <div className="subtopic-box-label">🧮 FORMULAS & PARAMETERS</div>
              <div className="subtopic-formulas-grid">
                {sub.formulas.map((formStr, fIdx) => (
                  <div key={fIdx} className="subtopic-formula-pill">
                    <MathText text={formStr} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 4. Worked Example */}
          {exampleObj && (exampleObj.problem || exampleObj.solution) && (
            <div className="subtopic-box subtopic-example-box">
              <div className="subtopic-box-label">💡 WORKED EXAMPLE</div>
              {exampleObj.problem && (
                <div className="example-problem">
                  <strong>Problem:</strong> <MathText text={exampleObj.problem} />
                </div>
              )}
              {exampleObj.solution && (
                <div className="example-solution">
                  <strong>Step-by-Step Solution:</strong> <MathText text={exampleObj.solution} />
                </div>
              )}
            </div>
          )}

          {/* 5. Comparison Table */}
          {sub.comparison_table && sub.comparison_table.includes('|') && (
            <div className="subtopic-box subtopic-table-box">
              <div className="subtopic-box-label">📊 KEY DISTINCTIONS & COMPARISONS</div>
              <FormattedContent content={sub.comparison_table} />
            </div>
          )}

          {/* 6. Common Mistakes & Exam Tips */}
          {((sub.common_mistakes && sub.common_mistakes.length > 0) || (sub.exam_tips && sub.exam_tips.length > 0)) && (
            <div className="subtopic-traps-row">
              {sub.common_mistakes && sub.common_mistakes.length > 0 && (
                <div className="trap-card trap-mistake">
                  <div className="trap-title">⚠️ COMMON MISTAKES & TRAPS</div>
                  <ul className="trap-list">
                    {sub.common_mistakes.map((m, mIdx) => (
                      <li key={mIdx}><MathText text={m} /></li>
                    ))}
                  </ul>
                </div>
              )}

              {sub.exam_tips && sub.exam_tips.length > 0 && (
                <div className="trap-card trap-tip">
                  <div className="trap-title">🎯 HIGH-YIELD EXAM TIPS</div>
                  <ul className="trap-list">
                    {sub.exam_tips.map((t, tIdx) => (
                      <li key={tIdx}><MathText text={t} /></li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* 7. Attached Figures & Diagrams (if any) */}
          {sub.figures && sub.figures.length > 0 && (
            <div className="subtopic-box subtopic-figures-box">
              <div className="subtopic-box-label">🎨 ATTACHED DIAGRAMS</div>
              {sub.figures.map((fig, figIdx) => (
                <div key={figIdx} className="figure-item">
                  {fig.image_url && <img src={fig.image_url} alt={fig.caption || 'Textbook Diagram'} className="subtopic-diagram-img" />}
                  <span className="figure-caption">{fig.caption || `Figure on Page ${fig.page || ''}`}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}


// ═══════════════════════════════════════════════════════════════════════════
// TOPIC QUICK CARD — 1-Screen Rapid Revision Sheet per Topic
// ═══════════════════════════════════════════════════════════════════════════

function TopicQuickCard({ topic, index, accent }) {
  return (
    <section
      className="quick-topic-card anime-section"
      id={`quick-${index}`}
      style={{
        '--anime-border': accent.border,
        '--anime-bg': accent.bg,
        '--anime-glow': accent.glow,
      }}
    >
      <div className="quick-topic-head">
        <div className="quick-topic-badge" style={{ background: accent.border }}>
          {accent.emoji} {String(index + 1).padStart(2, '0')}
        </div>
        <div className="quick-topic-titles">
          <span className="quick-topic-chapter">{topic.chapter}</span>
          <h3 className="quick-topic-name">{topic.topic}</h3>
        </div>
        {topic.source_pages?.length > 0 && (
          <span className="quick-page-pill">📖 Pages {topic.source_pages.join(', ')}</span>
        )}
      </div>

      {/* 5 to 8 crisp summary bullets */}
      {topic.bullets && topic.bullets.length > 0 && (
        <div className="quick-bullets-wrap">
          <ul className="quick-bullets-list">
            {topic.bullets.map((b, bIdx) => (
              <li key={bIdx}><MathText text={b} /></li>
            ))}
          </ul>
        </div>
      )}

      {/* Key Formulas */}
      {topic.key_formulas && topic.key_formulas.length > 0 && (
        <div className="quick-formulas-wrap">
          <div className="quick-subhead">⚡ ESSENTIAL FORMULAS</div>
          <div className="quick-formula-items">
            {topic.key_formulas.map((f, fIdx) => (
              <div key={fIdx} className="quick-formula-pill">
                <MathText text={f} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 1-Line Memory Trick / Mnemonic */}
      {topic.memory_trick && (
        <div className="quick-mnemonic-wrap">
          <div className="mnemonic-tag">🧠 MEMORY TRICK (MNEMONIC)</div>
          <div className="mnemonic-text"><MathText text={topic.memory_trick} /></div>
        </div>
      )}
    </section>
  )
}


// ═══════════════════════════════════════════════════════════════════════════
// NOTES PANEL — Table of Contents, KaTeX Math, & Collapsible Concepts
// ═══════════════════════════════════════════════════════════════════════════

function NotesPanel({ material, view, onCopy, onGenerate, actionLabel }) {
  const [copied, setCopied] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedMap, setExpandedMap] = useState({})
  const [allExpanded, setAllExpanded] = useState(true)

  const isQuick = view === 'quick-notes'
  const subtopics = material?.subtopics || []
  const topics = material?.topics || []
  const sections = material?.sections || []

  // Initialize or toggle expanded state
  const isSubtopicMode = !isQuick && subtopics.length > 0
  const isTopicQuickMode = isQuick && topics.length > 0

  useEffect(() => {
    // Default: expand all on load
    if (subtopics.length > 0) {
      const initMap = {}
      subtopics.forEach((_, i) => { initMap[i] = true })
      setExpandedMap(initMap)
      setAllExpanded(true)
    }
  }, [subtopics.length])

  if (!material) {
    return (
      <EmptyMaterial
        icon={Sparkles}
        title="Your notes are one tap away"
        detail="Lumio will structure your textbook into clear, sourced study sections with key formulas, worked examples, and concept breakdown."
        onGenerate={onGenerate}
        actionLabel={actionLabel}
      />
    )
  }

  const handleCopy = () => {
    onCopy()
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const toggleAll = () => {
    const nextState = !allExpanded
    setAllExpanded(nextState)
    const newMap = {}
    subtopics.forEach((_, i) => { newMap[i] = nextState })
    setExpandedMap(newMap)
  }

  const toggleSubtopic = (index) => {
    setExpandedMap((prev) => ({ ...prev, [index]: !prev[index] }))
  }

  /** Accent color palette */
  const accentColors = [
    { border: '#e85d2a', bg: 'rgba(232,93,42,0.05)', glow: 'rgba(232,93,42,0.18)', emoji: '🔥' },
    { border: '#347e72', bg: 'rgba(52,126,114,0.05)', glow: 'rgba(52,126,114,0.18)', emoji: '✨' },
    { border: '#dfb744', bg: 'rgba(223,183,68,0.06)', glow: 'rgba(223,183,68,0.18)', emoji: '⭐' },
    { border: '#7B68EE', bg: 'rgba(123,104,238,0.06)', glow: 'rgba(123,104,238,0.18)', emoji: '💜' },
    { border: '#c84535', bg: 'rgba(200,69,53,0.05)', glow: 'rgba(200,69,53,0.18)', emoji: '🌟' },
    { border: '#00A896', bg: 'rgba(0,168,150,0.06)', glow: 'rgba(0,168,150,0.18)', emoji: '🍀' },
  ]

  // Filter items in Table of Contents based on search term
  const filteredSubtopics = useMemo(() => {
    if (!searchTerm.trim()) return subtopics
    const q = searchTerm.toLowerCase()
    return subtopics.filter((s) =>
      s.subtopic.toLowerCase().includes(q) ||
      s.chapter.toLowerCase().includes(q) ||
      (s.topic && s.topic.toLowerCase().includes(q))
    )
  }, [subtopics, searchTerm])

  const filteredTopics = useMemo(() => {
    if (!searchTerm.trim()) return topics
    const q = searchTerm.toLowerCase()
    return topics.filter((t) =>
      t.topic.toLowerCase().includes(q) ||
      t.chapter.toLowerCase().includes(q)
    )
  }, [topics, searchTerm])

  return (
    <div className="notes-layout">
      {/* Sidebar Table of Contents (TOC) */}
      <aside className="notes-index-sidebar">
        <div className="toc-header">
          <span className="toc-title">TABLE OF CONTENTS</span>
          <span className="toc-count">
            {isSubtopicMode ? `${subtopics.length} SUBTOPICS` :
             isTopicQuickMode ? `${topics.length} TOPICS` :
             `${sections.length} SECTIONS`}
          </span>
        </div>

        {/* Search filter in Table of Contents */}
        {(isSubtopicMode || isTopicQuickMode) && (
          <div className="toc-search-wrap">
            <Search size={14} className="toc-search-icon" />
            <input
              type="text"
              placeholder={isSubtopicMode ? "Search 46 subtopics..." : "Search topics..."}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="toc-search-input"
            />
            {searchTerm && (
              <button className="toc-clear-btn" onClick={() => setSearchTerm('')}>
                <X size={12} />
              </button>
            )}
          </div>
        )}

        {/* Subtopic links tree */}
        <div className="toc-items-scroll">
          {isSubtopicMode && (
            filteredSubtopics.map((sub, idx) => {
              const origIdx = subtopics.indexOf(sub)
              return (
                <a
                  key={sub.subtopic_id || origIdx}
                  href={`#subtopic-${origIdx}`}
                  className="toc-subtopic-link"
                  onClick={(e) => {
                    e.preventDefault()
                    setExpandedMap((prev) => ({ ...prev, [origIdx]: true }))
                    document.getElementById(`subtopic-${origIdx}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                  }}
                >
                  <span className="toc-item-number">{String(origIdx + 1).padStart(2, '0')}</span>
                  <div className="toc-item-text">
                    <small className="toc-chapter-breadcrumb">{sub.chapter.replace(/^Chapter\s+\d+:\s*/i, '')}</small>
                    <b className="toc-subtopic-heading">{sub.subtopic}</b>
                  </div>
                  {sub.source_pages?.length > 0 && (
                    <span className="toc-page-pill">p.{sub.source_pages[0]}</span>
                  )}
                </a>
              )
            })
          )}

          {isTopicQuickMode && (
            filteredTopics.map((top, idx) => {
              const origIdx = topics.indexOf(top)
              return (
                <a
                  key={top.topic_id || origIdx}
                  href={`#quick-${origIdx}`}
                  className="toc-subtopic-link"
                  onClick={(e) => {
                    e.preventDefault()
                    document.getElementById(`quick-${origIdx}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                  }}
                >
                  <span className="toc-item-number">{String(origIdx + 1).padStart(2, '0')}</span>
                  <div className="toc-item-text">
                    <small className="toc-chapter-breadcrumb">{top.chapter.replace(/^Chapter\s+\d+:\s*/i, '')}</small>
                    <b className="toc-subtopic-heading">{top.topic}</b>
                  </div>
                  {top.source_pages?.length > 0 && (
                    <span className="toc-page-pill">p.{top.source_pages[0]}</span>
                  )}
                </a>
              )
            })
          )}

          {/* Fallback sections list if subtopics array is empty */}
          {!isSubtopicMode && !isTopicQuickMode && (
            sections.map((section, index) => (
              <a
                key={`${section.heading}-${index}`}
                href={`#note-${index}`}
                className="toc-subtopic-link"
                onClick={(e) => {
                  e.preventDefault()
                  document.getElementById(`note-${index}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                }}
              >
                <span className="toc-item-number">{String(index + 1).padStart(2, '0')}</span>
                <b className="toc-subtopic-heading">{section.heading}</b>
              </a>
            ))
          )}
        </div>

        <button className="text-action copy-action-btn" onClick={handleCopy}>
          {copied ? <><Check size={15} color="#3d7a51" /> Copied to clipboard!</> : <><FileText size={15} /> Copy notes</>}
        </button>
      </aside>

      {/* Main notes paper */}
      <article className="notes-paper anime-notes">
        {/* Decorative corner elements */}
        <div className="anime-corner anime-corner-tl">✦</div>
        <div className="anime-corner anime-corner-tr">❀</div>
        <div className="anime-corner anime-corner-bl">✿</div>
        <div className="anime-corner anime-corner-br">✦</div>
        <div className="anime-sparkle-strip" />

        {/* Header toolbar */}
        <div className="paper-topline anime-topline">
          <span><Sparkles size={14} /> ✨ {isQuick ? 'LUMIO RAPID REVISION' : 'LUMIO MASTER STUDY GUIDE'} ✨</span>
          <div className="topline-actions">
            {isSubtopicMode && (
              <button className="expand-all-btn" onClick={toggleAll}>
                {allExpanded ? <><ChevronUp size={14} /> Collapse all</> : <><ChevronDown size={14} /> Expand all</>}
              </button>
            )}
            <span className="topline-pill">
              🌟 {isSubtopicMode ? `${subtopics.length} SUBTOPICS` :
                  isTopicQuickMode ? `${topics.length} TOPICS` :
                  `${sections.length} SECTIONS`}
            </span>
          </div>
        </div>

        <h2 className="anime-title">{material.title}</h2>

        {/* View 1: Granular Deep Notes (Subtopics) */}
        {isSubtopicMode && (
          <div className="subtopics-container">
            {subtopics.map((sub, index) => {
              const accent = accentColors[index % accentColors.length]
              return (
                <SubtopicCard
                  key={sub.subtopic_id || index}
                  sub={sub}
                  index={index}
                  expanded={expandedMap[index] ?? true}
                  onToggle={() => toggleSubtopic(index)}
                  accent={accent}
                />
              )
            })}
          </div>
        )}

        {/* View 2: Quick Notes (Topic Revision Sheets) */}
        {isTopicQuickMode && (
          <div className="quick-topics-container">
            {topics.map((top, index) => {
              const accent = accentColors[index % accentColors.length]
              return (
                <TopicQuickCard
                  key={top.topic_id || index}
                  topic={top}
                  index={index}
                  accent={accent}
                />
              )
            })}
          </div>
        )}

        {/* View 3: Fallback Sections */}
        {!isSubtopicMode && !isTopicQuickMode && (
          sections.map((section, index) => {
            const accent = accentColors[index % accentColors.length]
            return (
              <section
                className="note-section anime-section"
                id={`note-${index}`}
                key={`${section.heading}-${index}`}
                style={{
                  '--anime-border': accent.border,
                  '--anime-bg': accent.bg,
                  '--anime-glow': accent.glow,
                }}
              >
                <div className="anime-badge" style={{ background: accent.border }}>
                  {accent.emoji}
                </div>
                <div className="note-section-head">
                  <span className="note-number anime-number" style={{ color: accent.border }}>
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <h3 style={{ color: accent.border }}>{section.heading}</h3>
                </div>
                <FormattedContent content={section.content} />
                {section.source_pages?.length > 0 && (
                  <div className="source-line anime-source" style={{ color: accent.border }}>
                    📖 SOURCE PAGES <span>{section.source_pages.join(' · ')}</span>
                  </div>
                )}
              </section>
            )
          })
        )}

        {/* Bottom footer decoration */}
        <div className="anime-footer">
          <span>🌈</span>
          <span>Made with ✨ by Lumio</span>
          <span>🌈</span>
        </div>
      </article>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════
// QUIZ PANEL
// ═══════════════════════════════════════════════════════════════════════════

function QuizPanel({ quiz, answers, setAnswers, submitted, setSubmitted, onRestart, onGenerate }) {
  if (!quiz) {
    return (
      <EmptyMaterial
        icon={CircleHelp}
        title="Make recall your superpower"
        detail="Generate an interactive practice quiz with multiple-choice, true/false, and short-answer questions grounded in your textbook."
        onGenerate={onGenerate}
        actionLabel="Generate quiz lab"
      />
    )
  }

  const questions = quiz.questions || []
  const answeredCount = Object.keys(answers).length
  const score = questions.filter(
    (item, index) => (answers[index] || '').trim().toLowerCase() === (item.answer || '').trim().toLowerCase()
  ).length

  return (
    <div className="quiz-wrap">
      {/* Toolbar showing question count and progress */}
      <div className="quiz-toolbar">
        <span>{questions.length} QUESTIONS <i /> {submitted ? `COMPLETED` : `${answeredCount} OF ${questions.length} ANSWERED`}</span>
        {submitted
          ? <span className="score-label">FINAL SCORE: <b>{score}/{questions.length}</b></span>
          : <button className="text-action" onClick={onRestart}><RotateCcw size={15} /> Reset</button>
        }
      </div>

      {/* Submitted Score Summary Celebration */}
      {submitted && (
        <div className="quiz-result-banner">
          <div className="score-badge">
            <strong>{score} / {questions.length}</strong>
            <span>{Math.round((score / (questions.length || 1)) * 100)}% Score</span>
          </div>
          <div className="score-feedback">
            <h4>{score === questions.length ? '🌟 Perfect score! Flawless recall!' : score >= questions.length * 0.75 ? '🎉 Great job! Solid understanding!' : '💪 Good effort! Review explanations below:'}</h4>
            <p>{score === questions.length ? 'You mastered every question in this textbook quiz.' : 'Check the detailed source-page explanations for any concepts you missed.'}</p>
          </div>
        </div>
      )}

      {/* Question list */}
      <div className="question-list">
        {questions.map((item, index) => {
          const rawOptions = item.type === 'true_false' ? ['True', 'False'] : (item.options || [])
          const isCorrect = (answers[index] || '').trim().toLowerCase() === (item.answer || '').trim().toLowerCase()

          return (
            <article className={`question-block ${submitted ? (isCorrect ? 'block-correct' : 'block-incorrect') : ''}`} key={`${index}-${item.question}`}>
              <div className="question-meta">
                <span>QUESTION {String(index + 1).padStart(2, '0')}</span>
                <span className={`difficulty difficulty-${item.difficulty || 'medium'}`}>{item.difficulty || 'medium'}</span>
                {item.source_pages?.length > 0 && <span className="quiz-source-tag">P. {item.source_pages.join(', ')}</span>}
              </div>
              <h3>{item.question}</h3>

              {/* Multiple choice / true-false options */}
              {item.type === 'multiple_choice' || item.type === 'true_false' ? (
                <div className="answer-options">
                  {rawOptions.map((option) => {
                    const chosen = answers[index] === option
                    const correct = option.toLowerCase() === (item.answer || '').toLowerCase()
                    return (
                      <button
                        key={option}
                        className={`answer-option ${chosen ? 'chosen' : ''} ${submitted && correct ? 'correct' : ''} ${submitted && chosen && !correct ? 'incorrect' : ''}`}
                        onClick={() => !submitted && setAnswers((current) => ({ ...current, [index]: option }))}
                        disabled={submitted}
                      >
                        <span className="option-mark">
                          {submitted && correct
                            ? <Check size={14} />
                            : (submitted && chosen && !correct
                              ? <X size={14} />
                              : String.fromCharCode(65 + rawOptions.indexOf(option)))
                          }
                        </span>
                        {option}
                      </button>
                    )
                  })}
                </div>
              ) : (
                /* Short answer input */
                <input
                  className={`short-answer ${submitted ? (isCorrect ? 'input-correct' : 'input-incorrect') : ''}`}
                  disabled={submitted}
                  value={answers[index] || ''}
                  onChange={(event) => setAnswers((current) => ({ ...current, [index]: event.target.value }))}
                  placeholder="Type your short answer here…"
                />
              )}

              {/* Explanation shown after submission */}
              {submitted && (
                <div className={`explanation ${isCorrect ? 'exp-correct' : 'exp-incorrect'}`}>
                  <b>{isCorrect ? '✓ Correct answer!' : `Expected answer: ${item.answer}`}</b>
                  <span>{item.explanation}</span>
                </div>
              )}
            </article>
          )
        })}
      </div>

      {/* Submit / retry footer */}
      <div className="quiz-footer">
        {submitted
          ? <button className="primary-button" onClick={onRestart}><RotateCcw size={16} /> Try quiz again</button>
          : <button className="primary-button" onClick={() => setSubmitted(true)} disabled={answeredCount === 0}><Check size={16} /> Check answers ({answeredCount}/{questions.length})</button>
        }
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════
// FLASHCARD PANEL (with Keyboard Controls)
// ═══════════════════════════════════════════════════════════════════════════

function FlashcardPanel({ deck, index, setIndex, flipped, setFlipped, onShuffle, onGenerate }) {
  const cardList = Array.isArray(deck?.cards) ? deck.cards : (Array.isArray(deck?.flashcards) ? deck.flashcards : [])

  const safeIndex = Math.min(Math.max(0, index), Math.max(0, cardList.length - 1))
  const card = cardList[safeIndex] || cardList[0]

  const move = (direction) => {
    if (!cardList.length) return
    setIndex((safeIndex + direction + cardList.length) % cardList.length)
    setFlipped(false)
  }

  // Keyboard navigation for power studying
  useEffect(() => {
    if (!cardList.length) return
    function handleKeyDown(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      if (e.code === 'Space' || e.key === 'Enter') {
        e.preventDefault()
        setFlipped((f) => !f)
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        move(1)
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        move(-1)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [safeIndex, cardList.length])

  if (!cardList.length) {
    return (
      <EmptyMaterial
        icon={Layers3}
        title="Small cards. Big recall."
        detail="Generate a focused active-recall deck from your textbook, then practice through it at your own speed."
        onGenerate={onGenerate}
        actionLabel="Generate flashcard deck"
      />
    )
  }

  return (
    <div className="flashcard-stage">
      <div className="flashcard-toolbar">
        <span>DECK: <b>{deck.title || 'Textbook Recall Deck'}</b></span>
        <div>
          <button className="text-action" onClick={onShuffle}><Shuffle size={15} /> Shuffle</button>
          <button className="text-action" onClick={() => { setIndex(0); setFlipped(false) }}><RotateCcw size={15} /> Restart</button>
        </div>
      </div>

      {/* Flashcard with 3D flip animation */}
      <button
        className={`flashcard ${flipped ? 'is-flipped' : ''}`}
        onClick={() => setFlipped(!flipped)}
        aria-label={flipped ? 'Show question' : 'Reveal answer'}
      >
        <span className="flashcard-corner" />
        <span className="card-kicker">{flipped ? '✓ THE ANSWER' : '⚡ QUICK RECALL'}</span>
        <strong>{flipped ? (card?.back || '') : (card?.front || '')}</strong>
        <span className="flip-hint">Tap or press <kbd>Space</kbd> to {flipped ? 'see question' : 'reveal answer'}</span>
        {card?.source_pages?.length > 0 && flipped && (
          <span className="card-source">SOURCE · P. {card.source_pages.join(', ')}</span>
        )}
      </button>

      {/* Navigation controls & progress */}
      <div className="card-controls">
        <button className="circle-control" onClick={() => move(-1)} title="Previous card (Left Arrow)"><ChevronLeft size={20} /></button>
        <div className="card-progress">
          <b>{String(safeIndex + 1).padStart(2, '0')}</b>
          <span> / {String(cardList.length).padStart(2, '0')}</span>
          <div className="progress-track">
            <span style={{ width: `${((safeIndex + 1) / cardList.length) * 100}%` }} />
          </div>
        </div>
        <button className="circle-control" onClick={() => move(1)} title="Next card (Right Arrow)"><ChevronRight size={20} /></button>
      </div>

      {/* Helpful keyboard shortcut guide */}
      <div className="keyboard-hints">
        <span><kbd>Space</kbd> Flip card</span>
        <span><kbd>→</kbd> Next card</span>
        <span><kbd>←</kbd> Previous card</span>
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════
// CHAT PANEL (with interactive suggestions & clear chat)
// ═══════════════════════════════════════════════════════════════════════════

function ChatPanel({ chat, chatInput, setChatInput, onSubmit, onAsk, onClear, busy, chatEnd }) {
  const sampleSuggestions = [
    "What are the core concepts and principles?",
    "Explain the most important formulas with examples",
    "Summarize the key takeaways for exam revision",
    "What are common mistakes or misconceptions in this chapter?"
  ]

  return (
    <div className="chat-shell">
      {chat.length > 0 && (
        <div className="chat-top-actions">
          <span>GROUNDED STUDY CONVERSATION</span>
          <button type="button" className="clear-chat-btn" onClick={onClear} title="Clear conversation history">
            <Trash2 size={13} /> Clear chat
          </button>
        </div>
      )}

      <div className="chat-messages">
        {/* Empty state with interactive suggestion buttons */}
        {chat.length === 0 && (
          <div className="chat-empty">
            <div className="chat-orbit"><BrainCircuit size={28} /></div>
            <h2>Let&apos;s untangle something.</h2>
            <p>Ask about a concept, a formula, or a page that deserves a second look.</p>
            <div className="suggestions">
              {sampleSuggestions.map((sug) => (
                <button
                  type="button"
                  key={sug}
                  className="suggestion-chip-btn"
                  onClick={() => onAsk(null, sug)}
                >
                  &ldquo;{sug}&rdquo;
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message history */}
        {chat.map((message, index) => (
          <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>
            <span className="message-avatar">
              {message.role === 'lumio' ? <Sparkles size={15} /> : 'Y'}
            </span>
            <div>
              <div className="message-author">{message.role === 'lumio' ? 'LUMIO TUTOR' : 'YOU'}</div>
              <p>{message.content || message.answer}</p>
              {message.source_pages?.length > 0 && (
                <div className="chat-sources">📖 TEXTBOOK CITATION · PAGES {message.source_pages.join(', ')}</div>
              )}
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {busy && (
          <div className="chat-message lumio">
            <span className="message-avatar"><Sparkles size={15} /></span>
            <div>
              <div className="message-author">LUMIO TUTOR</div>
              <p className="thinking"><i /><i /><i /></p>
            </div>
          </div>
        )}

        <div ref={chatEnd} />
      </div>

      {/* Chat input composer */}
      <form className="chat-composer" onSubmit={onSubmit}>
        <textarea
          value={chatInput}
          onChange={(event) => setChatInput(event.target.value)}
          placeholder="Ask anything about your textbook (press Enter to send)…"
          rows={1}
          maxLength={2000}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              event.currentTarget.form.requestSubmit()
            }
          }}
        />
        <button type="submit" disabled={!chatInput.trim() || busy} aria-label="Send question">
          <Send size={17} />
        </button>
        <span>ANSWERS GROUNDED STRICTLY IN YOUR UPLOADED TEXTBOOK</span>
      </form>

      {/* Founder Direct Feedback */}
      <div className="chat-founder-feedback">
        <span className="feedback-hint">Need help, found an issue, or have a suggestion?</span>
        <a
          href="mailto:chetanaybatta361@gmail.com?subject=Lumio%20Feedback%20for%20Founder&body=Hi%20Chetanay,%0D%0A%0D%0AHere%20is%20my%20feedback%20or%20question%20about%20Lumio:%0D%0A"
          className="feedback-founder-link"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Mail size={13} />
          <span>Send feedback to founder (chetanaybatta361@gmail.com)</span>
        </a>
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════
// EMPTY STATE PLACEHOLDER
// ═══════════════════════════════════════════════════════════════════════════

function EmptyMaterial({ icon: Icon, title, detail, onGenerate, actionLabel }) {
  return (
    <div className="empty-material">
      <div className="empty-mark"><Icon size={24} /></div>
      <h2>{title}</h2>
      <p>{detail}</p>
      {onGenerate && (
        <button type="button" className="primary-button empty-generate-btn" onClick={onGenerate}>
          <Sparkles size={16} /> {actionLabel || 'Generate now'}
        </button>
      )}
    </div>
  )
}