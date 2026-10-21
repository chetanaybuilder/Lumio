import { useEffect, useRef, useState } from 'react'
import {
  BookOpenText, BrainCircuit, Check, ChevronLeft, ChevronRight, CircleHelp,
  Download, FileText, Flame, Layers3, LoaderCircle, MessageCircle, RotateCcw,
  Send, Shuffle, Sparkles, Upload, X,
} from 'lucide-react'
import { closeSession, createSession, exportPdf, generate, getDocument, uploadDocument } from './api.js'

const tools = [
  { id: 'deep-notes', label: 'Deep notes', icon: BookOpenText },
  { id: 'quick-notes', label: 'Quick notes', icon: FileText },
  { id: 'quiz', label: 'Quiz lab', icon: CircleHelp },
  { id: 'flashcards', label: 'Flashcards', icon: Layers3 },
  { id: 'chat', label: 'Ask Lumio', icon: MessageCircle },
]
const materialRoutes = {
  'deep-notes': ['/api/study/deep-notes', 'deep-notes'],
  'quick-notes': ['/api/study/quick-notes', 'quick-notes'],
  quiz: ['/api/study/quiz', 'quiz'],
  flashcards: ['/api/study/flashcards', 'flashcards'],
}

export default function App() {
  const [token, setToken] = useState('')
  const [document, setDocument] = useState(null)
  const [view, setView] = useState('deep-notes')
  const [materials, setMaterials] = useState({})
  const [loading, setLoading] = useState('Starting your private study space…')
  const [error, setError] = useState('')
  const [chat, setChat] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [busyChat, setBusyChat] = useState(false)
  const [quizAnswers, setQuizAnswers] = useState({})
  const [quizSubmitted, setQuizSubmitted] = useState(false)
  const [cardIndex, setCardIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const fileInput = useRef(null)
  const chatEnd = useRef(null)

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

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chat, busyChat])

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
      setMaterials((current) => ({ ...current, [kind === 'quiz' ? id : id]: generated }))
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

  const currentTool = tools.find((tool) => tool.id === view) || tools[0]
  const loadingWorkspace = Boolean(loading)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => setView('deep-notes')} aria-label="Lumio home">
          <span className="brand-mark"><Flame size={21} strokeWidth={2.6} /></span>
          <span>Lumio<span className="brand-period">.</span></span>
        </button>
        <div className="side-label">YOUR WORKSPACE</div>
        <div className="document-chip">
          <span className="document-icon"><FileText size={17} /></span>
          <span className="document-meta">
            <strong>{document?.filename || 'No textbook yet'}</strong>
            <small>{document ? `${document.page_count} pages · Ready` : 'Start with a PDF'}</small>
          </span>
          {document && <span className="ready-dot" />}
        </div>
        <div className="side-label tools-label">STUDY TOOLS</div>
        <nav className="tool-nav" aria-label="Study tools">
          {tools.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav-item ${view === id ? 'active' : ''}`} onClick={() => openTool(id)} disabled={!document}>
              <Icon size={18} strokeWidth={1.9} /><span>{label}</span>
              {view === id && <span className="active-mark" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy-note"><span className="privacy-glyph">✳</span><span><b>Just your study space</b><small>Private, temporary session</small></span></div>
          {document && <button className="new-session" onClick={resetSession}><RotateCcw size={15} /> Start fresh</button>}
          <div className="sidebar-foot">MADE FOR THE NEXT BIG IDEA</div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><span className="crumb-slash">/</span><strong>{currentTool.label}</strong></div>
          <div className="top-actions">
            {document && <div className="status-pill"><span /> Textbook ready</div>}
            {document && <button className="icon-button upload-again" title="Start a new study session" onClick={resetSession}><Upload size={17} /><span>New textbook</span></button>}
          </div>
        </header>

        {error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss error"><X size={16} /></button></div>}
        {!document ? (
          <section className="welcome-view">
            <div className="welcome-copy">
              <div className="eyebrow"><span className="eyebrow-line" /> YOUR FOCUS, AMPLIFIED</div>
              <h1>Turn pages into<br /><em>aha</em> moments.</h1>
              <p>Bring a textbook. Leave with a study plan that actually feels like yours.</p>
            </div>
            <div className="upload-panel" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); onFile(event.dataTransfer.files[0]) }}>
              <div className="upload-art"><span className="orbit orbit-one" /><span className="orbit orbit-two" /><span className="upload-icon"><Upload size={25} /></span><span className="sparkle sparkle-one">✦</span><span className="sparkle sparkle-two">✳</span></div>
              <h2>Drop your textbook here</h2>
              <p>PDF only · Up to 20 MB · Up to 500 pages</p>
              <button className="primary-button" disabled={!token || loadingWorkspace} onClick={() => fileInput.current?.click()}>
                {loadingWorkspace ? <LoaderCircle className="spin" size={17} /> : <Upload size={17} />}{loadingWorkspace ? 'Getting things ready' : 'Choose a PDF'}
              </button>
              <input ref={fileInput} type="file" accept="application/pdf,.pdf" hidden onChange={(event) => onFile(event.target.files[0])} />
              {loadingWorkspace && token && <div className="upload-status" role="status" aria-live="polite"><LoaderCircle className="spin" size={15} />{loading}</div>}
              <div className="upload-assurance"><span>01</span> Private by design <i /> <span>02</span> No account needed</div>
            </div>
            <div className="how-row"><span className="how-title">A little less cramming.<br /><b>A lot more clarity.</b></span><div><span className="step-no">01</span><b>Bring your book</b><small>Start with the PDF you have.</small></div><div><span className="step-no">02</span><b>Pick your rhythm</b><small>Notes, quizzes, cards, or chat.</small></div><div><span className="step-no">03</span><b>Make it stick</b><small>Study the way you learn best.</small></div></div>
          </section>
        ) : (
          <section className="work-view">
            <div className="page-heading">
              <div><div className="eyebrow"><span className="eyebrow-line" /> STUDY STUDIO</div><h1>{view === 'deep-notes' ? 'Deep notes' : view === 'quick-notes' ? 'Quick notes' : view === 'quiz' ? 'Quiz lab' : view === 'flashcards' ? 'Flashcards' : 'Ask Lumio'}</h1><p>{view === 'chat' ? 'A textbook-grounded conversation, page by page.' : `Built from ${document.filename}`}</p></div>
              {materials[view] && view !== 'chat' && <button className="outline-button" onClick={() => download(view)}><Download size={16} /> Export PDF</button>}
            </div>
            {loadingWorkspace && <div className="loading-row"><LoaderCircle className="spin" size={18} />{loading}</div>}
            {!loadingWorkspace && view === 'chat' && <ChatPanel chat={chat} chatInput={chatInput} setChatInput={setChatInput} onSubmit={sendQuestion} busy={busyChat} chatEnd={chatEnd} />}
            {!loadingWorkspace && (view === 'deep-notes' || view === 'quick-notes') && <NotesPanel material={materials[view]} onCopy={() => navigator.clipboard?.writeText(materials[view]?.sections?.map((item) => `${item.heading}\n${item.content}`).join('\n\n') || '')} />}
            {!loadingWorkspace && view === 'quiz' && <QuizPanel quiz={materials.quiz} answers={quizAnswers} setAnswers={setQuizAnswers} submitted={quizSubmitted} setSubmitted={setQuizSubmitted} onRestart={() => { setQuizAnswers({}); setQuizSubmitted(false) }} />}
            {!loadingWorkspace && view === 'flashcards' && <FlashcardPanel deck={materials.flashcards} index={cardIndex} setIndex={setCardIndex} flipped={flipped} setFlipped={setFlipped} onShuffle={() => { const cards = [...(materials.flashcards?.cards || [])]; for (let i = cards.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [cards[i], cards[j]] = [cards[j], cards[i]] } setMaterials((current) => ({ ...current, flashcards: { ...current.flashcards, cards } })); setCardIndex(0); setFlipped(false) }} />}
          </section>
        )}
      </main>
    </div>
  )
}

function NotesPanel({ material, onCopy }) {
  if (!material) return <EmptyMaterial icon={Sparkles} title="Your notes are one tap away" detail="Lumio will shape the textbook into clear, sourced study notes." />
  return <div className="notes-layout"><aside className="notes-index"><span>IN THIS GUIDE</span>{material.sections.map((section, index) => <a key={`${section.heading}-${index}`} href={`#note-${index}`}>{String(index + 1).padStart(2, '0')} <b>{section.heading}</b></a>)}<button className="text-action" onClick={onCopy}><FileText size={15} /> Copy notes</button></aside><article className="notes-paper"><div className="paper-topline"><span><Sparkles size={14} /> LUMIO STUDY GUIDE</span><span>{material.sections.length} SECTIONS</span></div><h2>{material.title}</h2>{material.sections.map((section, index) => <section className={`note-section note-accent-${index % 4}`} id={`note-${index}`} key={`${section.heading}-${index}`}><div className="note-section-head"><span className="note-number">{String(index + 1).padStart(2, '0')}</span><h3>{section.heading}</h3></div><p>{section.content}</p>{section.source_pages?.length > 0 && <div className="source-line">SOURCE PAGES <span>{section.source_pages.join(' · ')}</span></div>}</section>)}</article></div>
}

function QuizPanel({ quiz, answers, setAnswers, submitted, setSubmitted, onRestart }) {
  if (!quiz) return <EmptyMaterial icon={CircleHelp} title="Make recall your superpower" detail="Build a textbook-based quiz, then check your answers and explanations." />
  const score = quiz.questions.filter((item, index) => (answers[index] || '').trim().toLowerCase() === item.answer.trim().toLowerCase()).length
  return <div className="quiz-wrap"><div className="quiz-toolbar"><span>{quiz.questions.length} QUESTIONS <i /> ANSWER AT YOUR OWN PACE</span>{submitted ? <span className="score-label">SCORE <b>{score}/{quiz.questions.length}</b></span> : <button className="text-action" onClick={onRestart}><RotateCcw size={15} /> Reset</button>}</div><div className="question-list">{quiz.questions.map((item, index) => <article className="question-block" key={`${index}-${item.question}`}><div className="question-meta"><span>QUESTION {String(index + 1).padStart(2, '0')}</span><span className={`difficulty difficulty-${item.difficulty}`}>{item.difficulty}</span></div><h3>{item.question}</h3>{item.type === 'multiple_choice' || item.type === 'true_false' ? <div className="answer-options">{(item.type === 'true_false' ? ['True', 'False'] : item.options).map((option) => { const chosen = answers[index] === option; const correct = option.toLowerCase() === item.answer.toLowerCase(); return <button key={option} className={`answer-option ${chosen ? 'chosen' : ''} ${submitted && correct ? 'correct' : ''} ${submitted && chosen && !correct ? 'incorrect' : ''}`} onClick={() => !submitted && setAnswers((current) => ({ ...current, [index]: option }))} disabled={submitted}><span className="option-mark">{submitted && correct ? <Check size={14} /> : String.fromCharCode(65 + (item.type === 'true_false' ? ['True', 'False'].indexOf(option) : item.options.indexOf(option)))}</span>{option}</button>})}</div> : <input className="short-answer" disabled={submitted} value={answers[index] || ''} onChange={(event) => setAnswers((current) => ({ ...current, [index]: event.target.value }))} placeholder="Write a short answer" />}{submitted && <div className="explanation"><b>{(answers[index] || '').trim().toLowerCase() === item.answer.trim().toLowerCase() ? 'That’s right.' : `Answer: ${item.answer}`}</b><span>{item.explanation}</span></div>}</article>)}</div><div className="quiz-footer">{submitted ? <button className="primary-button" onClick={onRestart}><RotateCcw size={16} /> Try again</button> : <button className="primary-button" onClick={() => setSubmitted(true)}><Check size={16} /> Check answers</button>}</div></div>
}

function FlashcardPanel({ deck, index, setIndex, flipped, setFlipped, onShuffle }) {
  if (!deck?.cards?.length) return <EmptyMaterial icon={Layers3} title="Small cards. Big recall." detail="Generate a focused deck from your textbook, then move through it at your pace." />
  const card = deck.cards[index]
  const move = (direction) => { setIndex((index + direction + deck.cards.length) % deck.cards.length); setFlipped(false) }
  return <div className="flashcard-stage"><div className="flashcard-toolbar"><span>DECK <b>{deck.title}</b></span><div><button className="text-action" onClick={onShuffle}><Shuffle size={15} /> Shuffle</button><button className="text-action" onClick={() => { setIndex(0); setFlipped(false) }}><RotateCcw size={15} /> Restart</button></div></div><button className={`flashcard ${flipped ? 'is-flipped' : ''}`} onClick={() => setFlipped(!flipped)} aria-label={flipped ? 'Show question' : 'Reveal answer'}><span className="flashcard-corner" /><span className="card-kicker">{flipped ? 'THE ANSWER' : 'QUICK RECALL'}</span><strong>{flipped ? card.back : card.front}</strong><span className="flip-hint">Tap to {flipped ? 'see question' : 'reveal answer'}</span>{card.source_pages?.length > 0 && flipped && <span className="card-source">SOURCE · P. {card.source_pages.join(', ')}</span>}</button><div className="card-controls"><button className="circle-control" onClick={() => move(-1)} title="Previous card"><ChevronLeft size={20} /></button><div className="card-progress"><b>{String(index + 1).padStart(2, '0')}</b><span> / {String(deck.cards.length).padStart(2, '0')}</span><div className="progress-track"><span style={{ width: `${((index + 1) / deck.cards.length) * 100}%` }} /></div></div><button className="circle-control" onClick={() => move(1)} title="Next card"><ChevronRight size={20} /></button></div></div>
}

function ChatPanel({ chat, chatInput, setChatInput, onSubmit, busy, chatEnd }) {
  return <div className="chat-shell"><div className="chat-messages">{chat.length === 0 && <div className="chat-empty"><div className="chat-orbit"><BrainCircuit size={28} /></div><h2>Let’s untangle something.</h2><p>Ask about a concept, a connection, or a page that deserves a second look.</p><div className="suggestions"><span>“What are the key ideas?”</span><span>“Explain this in simpler terms”</span></div></div>}{chat.map((message, index) => <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}><span className="message-avatar">{message.role === 'lumio' ? <Sparkles size={15} /> : 'Y'}</span><div><div className="message-author">{message.role === 'lumio' ? 'LUMIO' : 'YOU'}</div><p>{message.content || message.answer}</p>{message.source_pages?.length > 0 && <div className="chat-sources">TEXTBOOK · PAGES {message.source_pages.join(', ')}</div>}</div></div>)}{busy && <div className="chat-message lumio"><span className="message-avatar"><Sparkles size={15} /></span><div><div className="message-author">LUMIO</div><p className="thinking"><i /><i /><i /></p></div></div>}<div ref={chatEnd} /></div><form className="chat-composer" onSubmit={onSubmit}><textarea value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Ask something about your textbook…" rows={1} maxLength={2000} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form.requestSubmit() } }} /><button type="submit" disabled={!chatInput.trim() || busy} aria-label="Send question"><Send size={17} /></button><span>GROUNDED IN YOUR UPLOADED TEXTBOOK</span></form></div>
}

function EmptyMaterial({ icon: Icon, title, detail }) {
  return <div className="empty-material"><div className="empty-mark"><Icon size={22} /></div><h2>{title}</h2><p>{detail}</p></div>
}


// Feature panels stay local to the active temporary study session.