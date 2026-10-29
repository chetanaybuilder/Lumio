import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../lib/api';

export default function PaperView() {
  const navigate = useNavigate();
  const [mode, setMode] = useState('quick'); // 'quick' | 'full_mock'
  const [classLevel, setClassLevel] = useState(12);
  const [subject, setSubject] = useState('Mathematics');
  const [numQuestions, setNumQuestions] = useState(10);
  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [quizzes, setQuizzes] = useState([]);
  const [isLoadingQuizzes, setIsLoadingQuizzes] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const vaultDocs = await api.getDocuments();
        setDocuments(vaultDocs || []);
        if (vaultDocs && vaultDocs.length > 0) {
          setSelectedDocId(vaultDocs[0].id);
        }

        const quizList = await api.getQuizzes();
        setQuizzes(quizList || []);
      } catch (err) {
        console.error('Failed to load initial data:', err);
      } finally {
        setIsLoadingQuizzes(false);
      }
    }
    loadData();
  }, []);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setIsGenerating(true);
    setError(null);

    try {
      const payload = {
        mode,
        class_level: parseInt(classLevel, 10),
        subject,
        document_id: selectedDocId || undefined,
        num_questions: mode === 'quick' ? parseInt(numQuestions, 10) : undefined
      };

      const quiz = await api.createQuiz(payload);
      // Immediately navigate to exam attempt or refresh list
      if (quiz && quiz.id) {
        navigate(`/attempt/${quiz.id}`);
      }
    } catch (err) {
      console.error('Failed to generate paper:', err);
      setError(err.message || 'Generation failed. Please check backend status and parameters.');
      setIsGenerating(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Page Title & Breadcrumb */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="flex items-center space-x-2 text-xs text-zinc-400 mb-1">
            <Link to="/vault" className="hover:text-white transition">Vault</Link>
            <span>/</span>
            <span className="text-zinc-200">CBSE Paper Generator</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">CBSE Examination Papers</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Generate authentic board sample papers with Section A-E structure, exact marking schemes, and competency weights.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Paper Generator Form */}
        <div className="lg:col-span-1 bg-zinc-900/90 border border-white/10 rounded-2xl p-6 shadow-xl backdrop-blur-md self-start">
          <h2 className="text-lg font-bold text-white mb-4 flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-indigo-500"></span>
            <span>Configure Exam Paper</span>
          </h2>

          {error && (
            <div className="mb-4 p-3 bg-red-950/40 border border-red-500/40 rounded-xl text-xs text-red-300">
              {error}
            </div>
          )}

          <form onSubmit={handleGenerate} className="space-y-5">
            {/* Mode Selector */}
            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                Exam Mode
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setMode('quick')}
                  className={`py-2 px-3 text-xs font-medium rounded-xl border transition text-center ${
                    mode === 'quick'
                      ? 'bg-indigo-600/30 border-indigo-500 text-indigo-200'
                      : 'bg-zinc-800/50 border-white/5 text-zinc-400 hover:text-white'
                  }`}
                >
                  ⚡ Quick Drill
                </button>
                <button
                  type="button"
                  onClick={() => setMode('full_mock')}
                  className={`py-2 px-3 text-xs font-medium rounded-xl border transition text-center ${
                    mode === 'full_mock'
                      ? 'bg-indigo-600/30 border-indigo-500 text-indigo-200'
                      : 'bg-zinc-800/50 border-white/5 text-zinc-400 hover:text-white'
                  }`}
                >
                  🎯 Full Mock (80m)
                </button>
              </div>
            </div>

            {/* Class Level */}
            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">
                Class Level
              </label>
              <select
                value={classLevel}
                onChange={(e) => setClassLevel(e.target.value)}
                className="w-full bg-zinc-800/90 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value={10}>Class 10 CBSE</option>
                <option value={11}>Class 11 CBSE</option>
                <option value={12}>Class 12 CBSE</option>
              </select>
            </div>

            {/* Subject */}
            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">
                Subject
              </label>
              <select
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="w-full bg-zinc-800/90 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="Mathematics">Mathematics (041)</option>
                <option value="Physics">Physics (042)</option>
                <option value="Chemistry">Chemistry (043)</option>
              </select>
            </div>

            {/* Source Vault Document */}
            {documents.length > 0 && (
              <div>
                <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">
                  Scope Document (Optional)
                </label>
                <select
                  value={selectedDocId}
                  onChange={(e) => setSelectedDocId(e.target.value)}
                  className="w-full bg-zinc-800/90 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Full CBSE Syllabus Standard</option>
                  {documents.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.title} ({doc.page_count} pages)
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Quick Mode Count */}
            {mode === 'quick' && (
              <div>
                <div className="flex justify-between text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">
                  <span>Questions</span>
                  <span className="text-indigo-400 font-bold">{numQuestions} Qs</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="15"
                  value={numQuestions}
                  onChange={(e) => setNumQuestions(e.target.value)}
                  className="w-full accent-indigo-500 cursor-pointer"
                />
              </div>
            )}

            {/* Blueprint Overview banner */}
            {mode === 'full_mock' && (
              <div className="p-3 bg-indigo-950/30 border border-indigo-500/20 rounded-xl text-[11px] text-zinc-300 space-y-1">
                <div className="font-semibold text-indigo-300">CBSE Blueprint Standard:</div>
                <div>• Sec A: 20 MCQs (1m each)</div>
                <div>• Sec B: 5 Very Short Answers (2m each)</div>
                <div>• Sec C: 6 Short Answers (3m each)</div>
                <div>• Sec D: 4 Long Answers (5m each)</div>
                <div>• Sec E: 3 Case-Based (4m each)</div>
                <div className="pt-1 text-zinc-400 font-medium">Total: 80 Marks • 3 Hours</div>
              </div>
            )}

            <button
              type="submit"
              disabled={isGenerating}
              className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold text-sm transition shadow-lg shadow-indigo-600/30 disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              {isGenerating ? (
                <>
                  <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                  </svg>
                  <span>Assembling Paper Sections...</span>
                </>
              ) : (
                <span>Generate Exam Paper</span>
              )}
            </button>
          </form>
        </div>

        {/* Existing Papers List */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white">Generated Exam Papers</h2>
            <span className="text-xs text-zinc-400">{quizzes.length} papers available</span>
          </div>

          {isLoadingQuizzes ? (
            <div className="text-center py-12 text-zinc-500 text-sm">Loading papers...</div>
          ) : quizzes.length === 0 ? (
            <div className="bg-zinc-900/60 border border-dashed border-white/10 rounded-2xl p-12 text-center">
              <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center mx-auto mb-3 text-zinc-400 text-xl">
                📝
              </div>
              <h3 className="text-base font-semibold text-white mb-1">No Exam Papers Yet</h3>
              <p className="text-xs text-zinc-400 max-w-sm mx-auto mb-4">
                Configure the exam generator on the left to create your first CBSE Quick Drill or Full 80-Mark Mock Paper.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {quizzes.map((quiz) => (
                <div
                  key={quiz.id}
                  className="bg-zinc-900/80 border border-white/10 rounded-2xl p-5 hover:border-indigo-500/50 transition flex flex-col justify-between group shadow-lg"
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${
                        quiz.mode === 'full_mock'
                          ? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
                          : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                      }`}>
                        {quiz.mode === 'full_mock' ? 'Full Mock 80m' : 'Quick Drill'}
                      </span>
                      <span className="text-xs text-zinc-400 font-mono">
                        Class {quiz.class_level}
                      </span>
                    </div>

                    <h3 className="text-base font-bold text-white mb-1 group-hover:text-indigo-400 transition">
                      {quiz.subject}
                    </h3>

                    <div className="flex items-center space-x-4 text-xs text-zinc-400 mt-2">
                      <span>Total Marks: <strong className="text-zinc-200">{quiz.total_marks}</strong></span>
                      <span>Questions: <strong className="text-zinc-200">{quiz.question_count || (quiz.questions ? quiz.questions.length : '—')}</strong></span>
                    </div>
                  </div>

                  <div className="mt-6 pt-4 border-t border-white/5 flex items-center justify-between">
                    <span className="text-[11px] text-zinc-500">
                      {new Date(quiz.created_at).toLocaleDateString()}
                    </span>
                    <Link
                      to={`/attempt/${quiz.id}`}
                      className="px-4 py-2 rounded-xl bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-600 hover:text-white transition text-xs font-semibold"
                    >
                      Take Exam →
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
