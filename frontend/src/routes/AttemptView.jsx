import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { api } from '../lib/api';
import { Md } from '../lib/math';

export default function AttemptView() {
  const { id: quizId } = useParams();
  const navigate = useNavigate();

  const [quiz, setQuiz] = useState(null);
  const [attempt, setAttempt] = useState(null);
  const [answers, setAnswers] = useState({});
  const [currentSection, setCurrentSection] = useState('ALL');
  const [activeQuestionIndex, setActiveQuestionIndex] = useState(0);
  const [timeLeftSec, setTimeLeftSec] = useState(180 * 60); // default 3 hours
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [scratchpad, setScratchpad] = useState('');
  const [showScratchpad, setShowScratchpad] = useState(false);

  useEffect(() => {
    async function loadQuizAndStartAttempt() {
      try {
        const qData = await api.getQuiz(quizId);
        setQuiz(qData);

        // Calculate timer: 3 hours for full_mock, 25 mins for quick drill
        const durationSec = qData.mode === 'full_mock' ? 180 * 60 : 25 * 60;
        setTimeLeftSec(durationSec);

        // Start attempt session
        const att = await api.createQuizAttempt(quizId);
        setAttempt(att);
        if (att.answers) {
          setAnswers(att.answers);
        }
      } catch (err) {
        console.error('Failed to start attempt:', err);
        setError('Failed to load exam paper. Please ensure backend is running.');
      }
    }
    loadQuizAndStartAttempt();
  }, [quizId]);

  // Countdown timer
  useEffect(() => {
    if (!attempt || attempt.status === 'submitted') return;
    const timer = setInterval(() => {
      setTimeLeftSec((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          handleSubmitAttempt();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [attempt]);

  const formatTime = (seconds) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hrs > 0) {
      return `${hrs}h ${mins < 10 ? '0' : ''}${mins}m ${secs < 10 ? '0' : ''}${secs}s`;
    }
    return `${mins}m ${secs < 10 ? '0' : ''}${secs}s`;
  };

  const handleSelectOption = (qNo, optKey) => {
    setAnswers((prev) => ({
      ...prev,
      [qNo]: optKey
    }));
  };

  const handleTextAnswerChange = (qNo, text) => {
    setAnswers((prev) => ({
      ...prev,
      [qNo]: text
    }));
  };

  const handleSubmitAttempt = async () => {
    if (!attempt) return;
    setIsSubmitting(true);
    try {
      const timeSpent = (quiz.mode === 'full_mock' ? 180 * 60 : 25 * 60) - timeLeftSec;
      await api.submitQuizAttempt(attempt.id, {
        answers,
        time_spent_sec: Math.max(1, timeSpent),
        status: 'submitted'
      });
      // Navigate to evaluate / report
      navigate('/evaluate', { state: { attemptId: attempt.id, quizId } });
    } catch (err) {
      console.error('Submission failed:', err);
      setError('Failed to submit exam attempt. Try again.');
      setIsSubmitting(false);
    }
  };

  if (!quiz) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-zinc-400 text-sm">Preparing Exam Environment...</p>
        </div>
      </div>
    );
  }

  const questions = quiz.questions || [];
  const sections = ['ALL', ...new Set(questions.map((q) => q.section).filter(Boolean))];
  const filteredQuestions =
    currentSection === 'ALL'
      ? questions
      : questions.filter((q) => q.section === currentSection);

  const activeQuestion = filteredQuestions[activeQuestionIndex] || filteredQuestions[0];

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Top Header & Exam Status */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-white/10 mb-6 bg-zinc-950/70 p-4 rounded-2xl backdrop-blur-md">
        <div>
          <div className="flex items-center space-x-2 text-xs text-zinc-400 mb-1">
            <Link to="/paper" className="hover:text-white transition">← Exit to Papers</Link>
            <span>•</span>
            <span className="text-zinc-300 font-semibold uppercase">{quiz.mode} Mode</span>
          </div>
          <h1 className="text-xl font-bold text-white tracking-wide">
            {quiz.subject} — Class {quiz.class_level} Official Mock
          </h1>
        </div>

        <div className="flex items-center space-x-4">
          {/* Timer Display */}
          <div className="bg-zinc-900 border border-white/10 px-4 py-2 rounded-xl text-center">
            <div className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider">Time Remaining</div>
            <div className={`text-base font-mono font-bold ${
              timeLeftSec < 600 ? 'text-red-400 animate-pulse' : 'text-emerald-400'
            }`}>
              ⏱ {formatTime(timeLeftSec)}
            </div>
          </div>

          <button
            onClick={() => setShowScratchpad(!showScratchpad)}
            className="px-3 py-2 text-xs font-semibold rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-white/10 transition"
          >
            {showScratchpad ? 'Hide Scratchpad' : '📝 Math Scratchpad'}
          </button>

          <button
            onClick={handleSubmitAttempt}
            disabled={isSubmitting}
            className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs uppercase tracking-wider transition shadow-lg shadow-emerald-600/30 disabled:opacity-50"
          >
            {isSubmitting ? 'Evaluating...' : 'Submit Paper'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-950/40 border border-red-500/40 rounded-xl text-xs text-red-300">
          {error}
        </div>
      )}

      {/* Main Examination Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Question Area (3 cols) */}
        <div className="lg:col-span-3 space-y-6">
          {/* Section Filter Pills */}
          <div className="flex items-center space-x-2 overflow-x-auto pb-2">
            {sections.map((sec) => (
              <button
                key={sec}
                onClick={() => {
                  setCurrentSection(sec);
                  setActiveQuestionIndex(0);
                }}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold uppercase tracking-wider border transition ${
                  currentSection === sec
                    ? 'bg-indigo-600 border-indigo-500 text-white'
                    : 'bg-zinc-900/60 border-white/10 text-zinc-400 hover:text-white'
                }`}
              >
                {sec === 'ALL' ? 'All Sections' : `Section ${sec}`}
              </button>
            ))}
          </div>

          {/* Active Question Card */}
          {activeQuestion ? (
            <div className="bg-zinc-900/90 border border-white/10 rounded-2xl p-6 shadow-xl space-y-6">
              <div className="flex items-center justify-between pb-4 border-b border-white/10">
                <div className="flex items-center space-x-2">
                  <span className="px-2.5 py-1 rounded-lg bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-bold">
                    Q{activeQuestion.q_no}
                  </span>
                  {activeQuestion.section && (
                    <span className="text-xs text-zinc-400 uppercase font-semibold">
                      Section {activeQuestion.section} • {activeQuestion.q_type}
                    </span>
                  )}
                </div>
                <span className="text-xs px-2.5 py-1 rounded-full bg-zinc-800 text-zinc-300 font-mono">
                  {activeQuestion.marks} Mark{activeQuestion.marks > 1 ? 's' : ''}
                </span>
              </div>

              {/* Question Statement with KaTeX rendering */}
              <div className="text-base text-zinc-100 font-medium leading-relaxed">
                <Md>{activeQuestion.question_md}</Md>
              </div>

              {/* Options for MCQ / Assertion Reason */}
              {activeQuestion.options && Array.isArray(activeQuestion.options) && activeQuestion.options.length > 0 ? (
                <div className="space-y-3 pt-2">
                  <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Select Option:</div>
                  <div className="grid grid-cols-1 gap-2.5">
                    {activeQuestion.options.map((opt, idx) => {
                      const optLabel = typeof opt === 'string' ? opt : (opt.label || opt.text || JSON.stringify(opt));
                      const optKey = String.fromCharCode(65 + idx); // 'A', 'B', 'C', 'D'
                      const isSelected = answers[activeQuestion.q_no] === optKey;

                      return (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => handleSelectOption(activeQuestion.q_no, optKey)}
                          className={`p-3.5 rounded-xl border text-left flex items-start space-x-3 transition ${
                            isSelected
                              ? 'bg-indigo-600/30 border-indigo-500 text-white ring-1 ring-indigo-500'
                              : 'bg-zinc-800/60 border-white/5 text-zinc-300 hover:bg-zinc-800 hover:border-white/20'
                          }`}
                        >
                          <span className={`w-6 h-6 rounded-lg text-xs font-bold flex items-center justify-center border shrink-0 ${
                            isSelected
                              ? 'bg-indigo-600 text-white border-indigo-400'
                              : 'bg-zinc-900 text-zinc-400 border-white/10'
                          }`}>
                            {optKey}
                          </span>
                          <div className="flex-1 text-sm pt-0.5">
                            <Md>{optLabel}</Md>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : (
                /* Written response field for VSA, SA, LA */
                <div className="space-y-2 pt-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    <span>Your Step-by-Step Answer:</span>
                    <span className="text-[11px] text-zinc-500 font-normal">Supports KaTeX inline (e.g. $F = ma$)</span>
                  </div>
                  <textarea
                    rows={6}
                    value={answers[activeQuestion.q_no] || ''}
                    onChange={(e) => handleTextAnswerChange(activeQuestion.q_no, e.target.value)}
                    placeholder="Write your derivation, steps, or explanation here..."
                    className="w-full bg-zinc-950/80 border border-white/10 rounded-xl p-3 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
                  />
                  {answers[activeQuestion.q_no] && (
                    <div className="p-3 bg-zinc-950/40 rounded-xl border border-white/5">
                      <div className="text-[10px] text-zinc-500 uppercase font-bold mb-1">Live Preview:</div>
                      <Md>{answers[activeQuestion.q_no]}</Md>
                    </div>
                  )}
                </div>
              )}

              {/* Navigation within section */}
              <div className="flex items-center justify-between pt-4 border-t border-white/10">
                <button
                  type="button"
                  disabled={activeQuestionIndex === 0}
                  onClick={() => setActiveQuestionIndex((prev) => Math.max(0, prev - 1))}
                  className="px-4 py-2 rounded-xl bg-zinc-800 text-zinc-300 hover:text-white disabled:opacity-30 text-xs font-medium transition"
                >
                  ← Previous Question
                </button>
                <span className="text-xs text-zinc-500">
                  {activeQuestionIndex + 1} of {filteredQuestions.length}
                </span>
                <button
                  type="button"
                  disabled={activeQuestionIndex === filteredQuestions.length - 1}
                  onClick={() => setActiveQuestionIndex((prev) => Math.min(filteredQuestions.length - 1, prev + 1))}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-30 text-xs font-medium transition"
                >
                  Next Question →
                </button>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-zinc-500 bg-zinc-900/40 rounded-2xl">
              No questions found in this section.
            </div>
          )}
        </div>

        {/* Sidebar: Question Matrix & Scratchpad (1 col) */}
        <div className="space-y-6">
          {/* Question Navigator Palette */}
          <div className="bg-zinc-900/90 border border-white/10 rounded-2xl p-5 shadow-xl">
            <h3 className="text-xs font-bold text-zinc-300 uppercase tracking-wider mb-3">
              Question Palette
            </h3>
            <div className="grid grid-cols-5 gap-2">
              {filteredQuestions.map((q, idx) => {
                const isAnswered = Boolean(answers[q.q_no]);
                const isActive = idx === activeQuestionIndex;

                return (
                  <button
                    key={q.q_no}
                    onClick={() => setActiveQuestionIndex(idx)}
                    className={`h-9 rounded-lg text-xs font-bold transition flex items-center justify-center border ${
                      isActive
                        ? 'ring-2 ring-indigo-400 bg-indigo-600 text-white border-transparent'
                        : isAnswered
                        ? 'bg-emerald-600/30 text-emerald-300 border-emerald-500/40 hover:bg-emerald-600/50'
                        : 'bg-zinc-800 text-zinc-400 border-white/5 hover:text-white'
                    }`}
                  >
                    {q.q_no}
                  </button>
                );
              })}
            </div>

            <div className="mt-4 pt-3 border-t border-white/5 space-y-1.5 text-[11px] text-zinc-400">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded bg-emerald-500"></span>
                <span>Answered ({Object.keys(answers).length})</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded bg-zinc-700"></span>
                <span>Unattempted ({Math.max(0, questions.length - Object.keys(answers).length)})</span>
              </div>
            </div>
          </div>

          {/* Optional Scratchpad */}
          {showScratchpad && (
            <div className="bg-zinc-900/90 border border-white/10 rounded-2xl p-5 shadow-xl space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-zinc-300 uppercase tracking-wider">
                  LaTeX Scratchpad
                </h3>
                <button
                  onClick={() => setScratchpad('')}
                  className="text-[10px] text-zinc-400 hover:text-white"
                >
                  Clear
                </button>
              </div>
              <textarea
                rows={4}
                value={scratchpad}
                onChange={(e) => setScratchpad(e.target.value)}
                placeholder="Try writing LaTeX math, e.g. $\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$"
                className="w-full bg-zinc-950 border border-white/10 rounded-xl p-2.5 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none font-mono"
              />
              {scratchpad && (
                <div className="p-2.5 bg-zinc-950/60 rounded-xl border border-white/5 text-xs text-zinc-300">
                  <Md>{scratchpad}</Md>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
