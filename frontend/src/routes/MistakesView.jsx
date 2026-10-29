import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { Md } from '../lib/math';

const CATEGORY_MAP = {
  concept_gap: { label: 'Conceptual Gap', color: 'bg-rose-500/20 text-rose-300 border-rose-500/30' },
  formula_recall: { label: 'Formula Recall', color: 'bg-amber-500/20 text-amber-300 border-amber-500/30' },
  calculation_error: { label: 'Calculation Error', color: 'bg-blue-500/20 text-blue-300 border-blue-500/30' },
  unit_error: { label: 'Missing / Wrong Unit', color: 'bg-purple-500/20 text-purple-300 border-purple-500/30' },
  misread_question: { label: 'Misread Question', color: 'bg-pink-500/20 text-pink-300 border-pink-500/30' },
  incomplete_steps: { label: 'Incomplete Steps', color: 'bg-orange-500/20 text-orange-300 border-orange-500/30' },
  diagram_error: { label: 'Diagram / Label Error', color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' }
};

export default function MistakesView() {
  const [mistakes, setMistakes] = useState([]);
  const [filter, setFilter] = useState('unresolved'); // 'all' | 'unresolved' | 'resolved'
  const [isLoading, setIsLoading] = useState(true);
  const [activeDrill, setActiveDrill] = useState(null);
  const [drillAnswers, setDrillAnswers] = useState({});
  const [drillResult, setDrillResult] = useState(null);
  const [isDrilling, setIsDrilling] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadMistakes();
  }, []);

  const loadMistakes = async () => {
    try {
      const data = await api.getMistakes();
      setMistakes(data || []);
    } catch (err) {
      console.error('Failed to load mistakes:', err);
      setError('Could not load mistakes from VexoVault API.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartDrill = async (mistakeId) => {
    setIsDrilling(true);
    setError(null);
    try {
      const drill = await api.createMistakeDrill(mistakeId);
      setActiveDrill(drill);
      setDrillAnswers({});
      setDrillResult(null);
    } catch (err) {
      console.error('Failed to create drill:', err);
      setError('Failed to generate 3-question targeted drill.');
    } finally {
      setIsDrilling(false);
    }
  };

  const handleSubmitDrill = () => {
    if (!activeDrill) return;
    const questions = activeDrill.questions || [];
    let correctCount = 0;

    questions.forEach((q, idx) => {
      if (drillAnswers[idx] && drillAnswers[idx].trim().toLowerCase() === (q.correct_answer || '').trim().toLowerCase()) {
        correctCount += 1;
      }
    });

    const isResolved = correctCount >= 2;
    setDrillResult({
      score: correctCount,
      total: questions.length,
      isResolved
    });

    if (isResolved) {
      // Mark mistake resolved locally
      setMistakes((prev) =>
        prev.map((m) => (m.id === activeDrill.mistake_id ? { ...m, resolved: true } : m))
      );
    }
  };

  const filteredMistakes = mistakes.filter((m) => {
    if (filter === 'unresolved') return !m.resolved;
    if (filter === 'resolved') return m.resolved;
    return true;
  });

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Title & Stats */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center space-x-2 text-xs text-zinc-400 mb-1">
            <Link to="/vault" className="hover:text-white transition">Vault</Link>
            <span>/</span>
            <span className="text-zinc-200">Mistake Tracker</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">
            Targeted Mistake Drill Bank
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Categorized audit of every marks deduction. Complete 3-question micro-drills (score ≥ 2/3) to resolve weaknesses permanently.
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center space-x-2 bg-zinc-900 border border-white/10 p-1 rounded-xl">
          <button
            onClick={() => setFilter('unresolved')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              filter === 'unresolved' ? 'bg-indigo-600 text-white' : 'text-zinc-400 hover:text-white'
            }`}
          >
            Needs Resolution ({mistakes.filter((m) => !m.resolved).length})
          </button>
          <button
            onClick={() => setFilter('resolved')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              filter === 'resolved' ? 'bg-indigo-600 text-white' : 'text-zinc-400 hover:text-white'
            }`}
          >
            Resolved ({mistakes.filter((m) => m.resolved).length})
          </button>
          <button
            onClick={() => setFilter('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              filter === 'all' ? 'bg-indigo-600 text-white' : 'text-zinc-400 hover:text-white'
            }`}
          >
            All
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-950/40 border border-red-500/40 rounded-xl text-xs text-red-300">
          {error}
        </div>
      )}

      {/* Drill Active Modal / Overlay */}
      {activeDrill && (
        <div className="mb-8 p-6 bg-gradient-to-br from-indigo-950/60 to-zinc-900 border border-indigo-500/30 rounded-2xl shadow-2xl space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-white/10">
            <div>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                Active 3-Question Micro-Drill
              </span>
              <h2 className="text-lg font-bold text-white mt-1">Resolve Concept Weakness</h2>
            </div>
            <button
              onClick={() => setActiveDrill(null)}
              className="text-xs text-zinc-400 hover:text-white px-2 py-1 bg-zinc-800 rounded-lg"
            >
              ✕ Close Drill
            </button>
          </div>

          {drillResult ? (
            <div className="p-6 rounded-xl bg-zinc-900/90 border border-white/10 text-center space-y-3">
              <div className="text-3xl">
                {drillResult.isResolved ? '🎉' : '⚠️'}
              </div>
              <h3 className="text-lg font-bold text-white">
                {drillResult.isResolved ? 'Mistake Resolved!' : 'Keep Practicing'}
              </h3>
              <p className="text-xs text-zinc-300 max-w-sm mx-auto">
                You scored {drillResult.score} / {drillResult.total}.{' '}
                {drillResult.isResolved
                  ? 'Congratulations! You passed the CBSE standard threshold (≥ 2/3) and this mistake has been cleared.'
                  : 'You need at least 2/3 correct to resolve this mistake. Try reviewing the notes before attempting again.'}
              </p>
              <button
                onClick={() => setActiveDrill(null)}
                className="mt-2 px-5 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold"
              >
                Done
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {(activeDrill.questions || []).map((q, idx) => (
                <div key={idx} className="p-4 bg-zinc-900/80 rounded-xl border border-white/10 space-y-3">
                  <div className="flex items-center space-x-2">
                    <span className="w-6 h-6 rounded-full bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 text-xs font-bold flex items-center justify-center">
                      {idx + 1}
                    </span>
                    <span className="text-xs text-zinc-400 uppercase font-semibold">Drill Question</span>
                  </div>
                  <div className="text-sm text-zinc-100 font-medium leading-relaxed">
                    <Md>{q.question_md || q.question}</Md>
                  </div>
                  <input
                    type="text"
                    value={drillAnswers[idx] || ''}
                    onChange={(e) => setDrillAnswers({ ...drillAnswers, [idx]: e.target.value })}
                    placeholder="Enter your concise answer or formula..."
                    className="w-full bg-zinc-950 border border-white/10 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
              ))}

              <button
                onClick={handleSubmitDrill}
                className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs uppercase tracking-wider transition shadow-lg shadow-emerald-600/30"
              >
                Submit Micro-Drill (Check Answers)
              </button>
            </div>
          )}
        </div>
      )}

      {/* Mistakes Grid */}
      {isLoading ? (
        <div className="text-center py-16 text-zinc-500 text-sm">Loading mistake catalog...</div>
      ) : filteredMistakes.length === 0 ? (
        <div className="bg-zinc-900/60 border border-dashed border-white/10 rounded-2xl p-16 text-center">
          <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center mx-auto mb-3 text-zinc-400 text-xl">
            ✨
          </div>
          <h3 className="text-base font-semibold text-white mb-1">
            {filter === 'unresolved' ? 'Zero Unresolved Mistakes!' : 'No Mistakes Recorded'}
          </h3>
          <p className="text-xs text-zinc-400 max-w-sm mx-auto">
            {filter === 'unresolved'
              ? 'Awesome job! All audited mistakes have been resolved through micro-drills.'
              : 'As you submit exam papers and answer evaluations, incorrect steps are automatically recorded here for targeted practice.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredMistakes.map((mistake) => {
            const cat = CATEGORY_MAP[mistake.category] || {
              label: mistake.category,
              color: 'bg-zinc-500/20 text-zinc-300 border-zinc-500/30'
            };

            return (
              <div
                key={mistake.id}
                className={`rounded-2xl border p-5 shadow-lg transition flex flex-col justify-between ${
                  mistake.resolved
                    ? 'bg-zinc-950/60 border-white/5 opacity-75'
                    : 'bg-zinc-900/90 border-white/10 hover:border-indigo-500/40'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${cat.color}`}>
                      {cat.label}
                    </span>
                    <div className="flex items-center space-x-2 text-xs">
                      {mistake.times_missed > 1 && (
                        <span className="text-rose-400 font-bold bg-rose-950/40 px-2 py-0.5 rounded-full border border-rose-500/20 text-[10px]">
                          Missed {mistake.times_missed}×
                        </span>
                      )}
                      <span className={`text-[11px] font-semibold ${mistake.resolved ? 'text-emerald-400' : 'text-amber-400'}`}>
                        {mistake.resolved ? '✓ Resolved' : '● Action Required'}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-2 text-xs mb-4">
                    {mistake.student_answer && (
                      <div className="text-zinc-400">
                        <span className="font-semibold text-rose-300">Your prior answer:</span>{' '}
                        <span className="line-through">{mistake.student_answer}</span>
                      </div>
                    )}
                    <div className="text-zinc-300">
                      <span className="font-semibold text-emerald-300">Correct standard:</span>{' '}
                      <Md>{mistake.correct_answer}</Md>
                    </div>
                    {mistake.explanation_md && (
                      <div className="text-zinc-400 bg-zinc-950/50 p-3 rounded-xl border border-white/5 leading-relaxed">
                        <Md>{mistake.explanation_md}</Md>
                      </div>
                    )}
                  </div>
                </div>

                <div className="pt-3 border-t border-white/5 flex items-center justify-between">
                  <span className="text-[10px] text-zinc-500">
                    Recorded {new Date(mistake.created_at).toLocaleDateString()}
                  </span>
                  {!mistake.resolved && (
                    <button
                      onClick={() => handleStartDrill(mistake.id)}
                      disabled={isDrilling}
                      className="px-3.5 py-1.5 rounded-xl bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-600 hover:text-white transition text-xs font-semibold shadow-md"
                    >
                      {isDrilling ? 'Generating...' : '⚡ Practice Drill (3 Qs)'}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
