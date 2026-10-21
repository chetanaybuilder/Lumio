/**
 * App Component — Lumio Frontend
 * ================================
 *
 * The root React component that orchestrates the entire Lumio study
 * workspace.  It manages:
 *
 * - **Session lifecycle** — automatic creation, restoration from
 *   `sessionStorage`, and explicit reset ("Start fresh").
 * - **PDF upload** — drag-and-drop or file picker, with real-time
 *   status feedback.
 * - **Study tools** — deep notes, quick notes, quiz lab, flashcards,
 *   and Ask Lumio chat, each rendered by a dedicated panel component.
 * - **PDF export** — download any generated material as a styled PDF.
 *
 * State is intentionally kept in a single component to avoid prop-
 * drilling complexity in this focused, single-page study workspace.
 */

import { useEffect, useRef, useState } from 'react'
import {
  BookOpenText, BrainCircuit, Check, ChevronLeft, ChevronRight, CircleHelp,
  Download, FileText, Flame, Layers3, LoaderCircle, Mail, MessageCircle, RotateCcw,
  Send, Shuffle, Sparkles, Upload, X,
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
        // Stale session — clear and create a fresh one below.
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
    try { if (token) await closeSession(token) } catch { /* expiry cleanup remains server-side */ }
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
  // File upload handler
  // -------------------------------------------------------------------------
  async function onFile(file) {
    if (!file || !token) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Choose a PDF textbook to continue.')
      return
    }
    setError('')
    setLoading('Reading your textbook and preparing its pages…')
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
  async function sendQuestion(event) {
    event.preventDefault()
    const question = chatInput.trim()
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
              <p>Bring a textbook. Leave with a study plan that actually feels like yours.</p>
            </div>
            <div
              className="upload-panel"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => { event.preventDefault(); onFile(event.dataTransfer.files[0]) }}
            >
              <div className="upload-art">
                <span className="orbit orbit-one" />
                <span className="orbit orbit-two" />
                <span className="upload-icon"><Upload size={25} /></span>
                <span className="sparkle sparkle-one">✦</span>
                <span className="sparkle sparkle-two">✳</span>
              </div>
              <h2>Drop your textbook here</h2>
              <p>PDF only · Up to 20 MB · Up to 500 pages</p>
              <button className="primary-button" disabled={!token || loadingWorkspace} onClick={() => fileInput.current?.click()}>
                {loadingWorkspace ? <LoaderCircle className="spin" size={17} /> : <Upload size={17} />}
                {loadingWorkspace ? 'Getting things ready' : 'Choose a PDF'}
              </button>
              <input ref={fileInput} type="file" accept="application/pdf,.pdf" hidden onChange={(event) => onFile(event.target.files[0])} />
              {loadingWorkspace && token && (
                <div className="upload-status" role="status" aria-live="polite">
                  <LoaderCircle className="spin" size={15} />{loading}
                </div>
              )}
              <div className="upload-assurance">
                <span>01</span> Private by design <i /> <span>02</span> No account needed
              </div>
            </div>
            <div className="how-row">
              <span className="how-title">A little less cramming.<br /><b>A lot more clarity.</b></span>
              <div><span className="step-no">01</span><b>Bring your book</b><small>Start with the PDF you have.</small></div>
              <div><span className="step-no">02</span><b>Pick your rhythm</b><small>Notes, quizzes, cards, or chat.</small></div>
              <div><span className="step-no">03</span><b>Make it stick</b><small>Study the way you learn best.</small></div>
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
              <ChatPanel chat={chat} chatInput={chatInput} setChatInput={setChatInput} onSubmit={sendQuestion} busy={busyChat} chatEnd={chatEnd} />
            )}
            {!loadingWorkspace && (view === 'deep-notes' || view === 'quick-notes') && (
              <NotesPanel
                material={materials[view]}
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
// NOTES PANEL — Anime-bordered colorful study notes
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Renders generated study notes with colorful anime-style borders,
 * decorative corner accents, and vibrant section styling.
 *
 * @param {object}   props.material - The generated notes data.
 * @param {function} props.onCopy   - Callback to copy notes to clipboard.
 */
function NotesPanel({ material, onCopy }) {
  if (!material) {
    return (
      <EmptyMaterial
        icon={Sparkles}
        title="Your notes are one tap away"
        detail="Lumio will shape the textbook into clear, sourced study notes."
      />
    )
  }

  /** Accent color palette for anime-style section borders */
  const accentColors = [
    { border: '#FF6B9D', bg: 'rgba(255,107,157,0.06)', glow: 'rgba(255,107,157,0.2)', emoji: '🌸' },
    { border: '#00D2FF', bg: 'rgba(0,210,255,0.06)', glow: 'rgba(0,210,255,0.2)', emoji: '✨' },
    { border: '#FFB347', bg: 'rgba(255,179,71,0.06)', glow: 'rgba(255,179,71,0.2)', emoji: '🔥' },
    { border: '#7B68EE', bg: 'rgba(123,104,238,0.06)', glow: 'rgba(123,104,238,0.2)', emoji: '💜' },
    { border: '#50C878', bg: 'rgba(80,200,120,0.06)', glow: 'rgba(80,200,120,0.2)', emoji: '🍀' },
    { border: '#FF69B4', bg: 'rgba(255,105,180,0.06)', glow: 'rgba(255,105,180,0.2)', emoji: '🎀' },
  ]

  return (
    <div className="notes-layout">
      {/* Side index navigation */}
      <aside className="notes-index">
        <span>IN THIS GUIDE</span>
        {material.sections.map((section, index) => (
          <a key={`${section.heading}-${index}`} href={`#note-${index}`}>
            {String(index + 1).padStart(2, '0')} <b>{section.heading}</b>
          </a>
        ))}
        <button className="text-action" onClick={onCopy}><FileText size={15} /> Copy notes</button>
      </aside>

      {/* Anime-bordered notes paper */}
      <article className="notes-paper anime-notes">
        {/* Decorative anime corner elements */}
        <div className="anime-corner anime-corner-tl">✦</div>
        <div className="anime-corner anime-corner-tr">❀</div>
        <div className="anime-corner anime-corner-bl">✿</div>
        <div className="anime-corner anime-corner-br">✦</div>
        <div className="anime-sparkle-strip" />

        {/* Header */}
        <div className="paper-topline anime-topline">
          <span><Sparkles size={14} /> ✨ LUMIO STUDY GUIDE ✨</span>
          <span>🌟 {material.sections.length} SECTIONS</span>
        </div>
        <h2 className="anime-title">{material.title}</h2>

        {/* Note sections with colorful anime borders */}
        {material.sections.map((section, index) => {
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
              {/* Decorative anime badge */}
              <div className="anime-badge" style={{ background: accent.border }}>
                {accent.emoji}
              </div>

              <div className="note-section-head">
                <span className="note-number anime-number" style={{ color: accent.border }}>
                  {String(index + 1).padStart(2, '0')}
                </span>
                <h3 style={{ color: accent.border }}>{section.heading}</h3>
              </div>
              <p>{section.content}</p>
              {section.source_pages?.length > 0 && (
                <div className="source-line anime-source" style={{ color: accent.border }}>
                  📖 SOURCE PAGES <span>{section.source_pages.join(' · ')}</span>
                </div>
              )}
            </section>
          )
        })}

        {/* Bottom anime decoration */}
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

/**
 * Interactive quiz with answer selection, submission, and scoring.
 *
 * @param {object}   props.quiz        - The generated quiz data.
 * @param {object}   props.answers     - Current answer selections by index.
 * @param {function} props.setAnswers  - State setter for answers.
 * @param {boolean}  props.submitted   - Whether answers have been submitted.
 * @param {function} props.setSubmitted - State setter for submission flag.
 * @param {function} props.onRestart   - Reset quiz to try again.
 */
function QuizPanel({ quiz, answers, setAnswers, submitted, setSubmitted, onRestart }) {
  if (!quiz) {
    return (
      <EmptyMaterial
        icon={CircleHelp}
        title="Make recall your superpower"
        detail="Build a textbook-based quiz, then check your answers and explanations."
      />
    )
  }

  // Calculate the score after submission.
  const score = quiz.questions.filter(
    (item, index) => (answers[index] || '').trim().toLowerCase() === item.answer.trim().toLowerCase()
  ).length

  return (
    <div className="quiz-wrap">
      {/* Toolbar showing question count and score */}
      <div className="quiz-toolbar">
        <span>{quiz.questions.length} QUESTIONS <i /> ANSWER AT YOUR OWN PACE</span>
        {submitted
          ? <span className="score-label">SCORE <b>{score}/{quiz.questions.length}</b></span>
          : <button className="text-action" onClick={onRestart}><RotateCcw size={15} /> Reset</button>
        }
      </div>

      {/* Question list */}
      <div className="question-list">
        {quiz.questions.map((item, index) => (
          <article className="question-block" key={`${index}-${item.question}`}>
            <div className="question-meta">
              <span>QUESTION {String(index + 1).padStart(2, '0')}</span>
              <span className={`difficulty difficulty-${item.difficulty}`}>{item.difficulty}</span>
            </div>
            <h3>{item.question}</h3>

            {/* Multiple choice / true-false options */}
            {item.type === 'multiple_choice' || item.type === 'true_false' ? (
              <div className="answer-options">
                {(item.type === 'true_false' ? ['True', 'False'] : item.options).map((option) => {
                  const chosen = answers[index] === option
                  const correct = option.toLowerCase() === item.answer.toLowerCase()
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
                          : String.fromCharCode(65 + (item.type === 'true_false' ? ['True', 'False'].indexOf(option) : item.options.indexOf(option)))
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
                className="short-answer"
                disabled={submitted}
                value={answers[index] || ''}
                onChange={(event) => setAnswers((current) => ({ ...current, [index]: event.target.value }))}
                placeholder="Write a short answer"
              />
            )}

            {/* Explanation shown after submission */}
            {submitted && (
              <div className="explanation">
                <b>{(answers[index] || '').trim().toLowerCase() === item.answer.trim().toLowerCase()
                  ? 'That\u2019s right.'
                  : `Answer: ${item.answer}`}</b>
                <span>{item.explanation}</span>
              </div>
            )}
          </article>
        ))}
      </div>

      {/* Submit / retry footer */}
      <div className="quiz-footer">
        {submitted
          ? <button className="primary-button" onClick={onRestart}><RotateCcw size={16} /> Try again</button>
          : <button className="primary-button" onClick={() => setSubmitted(true)}><Check size={16} /> Check answers</button>
        }
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════
// FLASHCARD PANEL
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Interactive flashcard deck with flip, navigate, shuffle, and restart.
 *
 * @param {object}   props.deck      - The generated flashcard deck data.
 * @param {number}   props.index     - Current card index.
 * @param {function} props.setIndex  - State setter for card index.
 * @param {boolean}  props.flipped   - Whether the current card is flipped.
 * @param {function} props.setFlipped - State setter for flip state.
 * @param {function} props.onShuffle - Randomize the card order.
 */
function FlashcardPanel({ deck, index, setIndex, flipped, setFlipped, onShuffle }) {
  const cardList = Array.isArray(deck?.cards) ? deck.cards : (Array.isArray(deck?.flashcards) ? deck.flashcards : [])

  if (!cardList.length) {
    return (
      <EmptyMaterial
        icon={Layers3}
        title="Small cards. Big recall."
        detail="Generate a focused deck from your textbook, then move through it at your pace."
      />
    )
  }

  const safeIndex = Math.min(Math.max(0, index), cardList.length - 1)
  const card = cardList[safeIndex] || cardList[0]
  const move = (direction) => {
    setIndex((safeIndex + direction + cardList.length) % cardList.length)
    setFlipped(false)
  }

  return (
    <div className="flashcard-stage">
      <div className="flashcard-toolbar">
        <span>DECK <b>{deck.title}</b></span>
        <div>
          <button className="text-action" onClick={onShuffle}><Shuffle size={15} /> Shuffle</button>
          <button className="text-action" onClick={() => { setIndex(0); setFlipped(false) }}><RotateCcw size={15} /> Restart</button>
        </div>
      </div>

      {/* Flashcard with flip animation */}
      <button
        className={`flashcard ${flipped ? 'is-flipped' : ''}`}
        onClick={() => setFlipped(!flipped)}
        aria-label={flipped ? 'Show question' : 'Reveal answer'}
      >
        <span className="flashcard-corner" />
        <span className="card-kicker">{flipped ? 'THE ANSWER' : 'QUICK RECALL'}</span>
        <strong>{flipped ? card.back : card.front}</strong>
        <span className="flip-hint">Tap to {flipped ? 'see question' : 'reveal answer'}</span>
        {card.source_pages?.length > 0 && flipped && (
          <span className="card-source">SOURCE · P. {card.source_pages.join(', ')}</span>
        )}
      </button>

      {/* Navigation controls */}
      <div className="card-controls">
        <button className="circle-control" onClick={() => move(-1)} title="Previous card"><ChevronLeft size={20} /></button>
        <div className="card-progress">
          <b>{String(safeIndex + 1).padStart(2, '0')}</b>
          <span> / {String(cardList.length).padStart(2, '0')}</span>
          <div className="progress-track">
            <span style={{ width: `${((safeIndex + 1) / cardList.length) * 100}%` }} />
          </div>
        </div>
        <button className="circle-control" onClick={() => move(1)} title="Next card"><ChevronRight size={20} /></button>
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════
// CHAT PANEL
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Conversational chat interface for Ask Lumio — textbook-grounded Q&A.
 *
 * @param {array}    props.chat         - Message history.
 * @param {string}   props.chatInput    - Current input value.
 * @param {function} props.setChatInput - State setter for input.
 * @param {function} props.onSubmit     - Form submit handler.
 * @param {boolean}  props.busy         - Whether a response is pending.
 * @param {object}   props.chatEnd      - Ref for auto-scroll target.
 */
function ChatPanel({ chat, chatInput, setChatInput, onSubmit, busy, chatEnd }) {
  return (
    <div className="chat-shell">
      <div className="chat-messages">
        {/* Empty state with suggested questions */}
        {chat.length === 0 && (
          <div className="chat-empty">
            <div className="chat-orbit"><BrainCircuit size={28} /></div>
            <h2>Let&apos;s untangle something.</h2>
            <p>Ask about a concept, a connection, or a page that deserves a second look.</p>
            <div className="suggestions">
              <span>&ldquo;What are the key ideas?&rdquo;</span>
              <span>&ldquo;Explain this in simpler terms&rdquo;</span>
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
              <div className="message-author">{message.role === 'lumio' ? 'LUMIO' : 'YOU'}</div>
              <p>{message.content || message.answer}</p>
              {message.source_pages?.length > 0 && (
                <div className="chat-sources">TEXTBOOK · PAGES {message.source_pages.join(', ')}</div>
              )}
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {busy && (
          <div className="chat-message lumio">
            <span className="message-avatar"><Sparkles size={15} /></span>
            <div>
              <div className="message-author">LUMIO</div>
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
          placeholder="Ask something about your textbook…"
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
        <span>GROUNDED IN YOUR UPLOADED TEXTBOOK</span>
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

/**
 * Placeholder shown when a study tool has not yet been generated.
 *
 * @param {Component} props.icon   - Lucide icon component.
 * @param {string}    props.title  - Placeholder heading.
 * @param {string}    props.detail - Descriptive subtext.
 */
function EmptyMaterial({ icon: Icon, title, detail }) {
  return (
    <div className="empty-material">
      <div className="empty-mark"><Icon size={22} /></div>
      <h2>{title}</h2>
      <p>{detail}</p>
    </div>
  )
}


// Feature panels stay local to the active temporary study session.