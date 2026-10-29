import React, { useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { api } from '../lib/api';
import { Md } from '../lib/math';

export default function EvaluateView() {
  const location = useLocation();
  const [questionText, setQuestionText] = useState('');
  const [answerText, setAnswerText] = useState('');
  const [maxMarks, setMaxMarks] = useState(5);
  const [evaluation, setEvaluation] = useState(null);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // If navigated from an attempt with state
    if (location.state && location.state.attemptId) {
      // Auto-load sample prompt or recent evaluation
      setQuestionText("Derive an expression for the magnetic field at a point on the axis of a circular current loop using Biot-Savart Law.");
      setAnswerText("Using Biot-Savart law: dB = (mu_0 / 4pi) * (I dl sin theta) / r^2. Since theta = 90 deg, dB = (mu_0 / 4pi) * (I dl / r^2). Integrating around the loop yields B = (mu_0 * I * R^2) / (2 * (R^2 + x^2)^(3/2)).");
    }
  }, [location.state]);

  const handleEvaluate = async (e) => {
    e.preventDefault();
    if (!questionText.trim() || !answerText.trim()) return;

    setIsEvaluating(true);
    setError(null);

    try {
      const res = await api.evaluateAnswer({
        question_text: questionText.trim(),
        answer_text: answerText.trim(),
        max_marks: parseFloat(maxMarks)
      });
      setEvaluation(res);
    } catch (err) {
      console.error('Evaluation failed:', err);
      setError(err.message || 'Evaluation failed. Ensure backend service is reachable.');
    } finally {
      setIsEvaluating(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Title & Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="flex items-center space-x-2 text-xs text-zinc-400 mb-1">
            <Link to="/vault" className="hover:text-white transition">Vault</Link>
            <span>/</span>
            <span className="text-zinc-200">Marks Improvement AI</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">
            CBSE Step-by-Step Marks Evaluator
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Audit any answer against official CBSE step-marking schemes. Identifies missing derivation steps, unit errors, and unearned half-marks.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Input Form (5 cols) */}
        <div className="lg:col-span-5 bg-zinc-900/90 border border-white/10 rounded-2xl p-6 shadow-xl backdrop-blur-md self-start space-y-4">
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
            <span>Input Question & Response</span>
          </h2>

          {error && (
            <div className="p-3 bg-red-950/40 border border-red-500/40 rounded-xl text-xs text-red-300">
              {error}
            </div>
          )}

          <form onSubmit={handleEvaluate} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">
                Question Statement
              </label>
              <textarea
                rows={3}
                value={questionText}
                onChange={(e) => setQuestionText(e.target.value)}
                placeholder="e.g. State and prove Gauss's Theorem in Electrostatics..."
                className="w-full bg-zinc-800/80 border border-white/10 rounded-xl p-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                  Maximum Marks
                </label>
                <span className="text-xs font-bold text-indigo-400">{maxMarks} Marks</span>
              </div>
              <input
                type="number"
                min="1"
                max="10"
                step="0.5"
                value={maxMarks}
                onChange={(e) => setMaxMarks(e.target.value)}
                className="w-full bg-zinc-800/80 border border-white/10 rounded-xl p-2.5 text-sm text-white focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">
                Student Written Answer
              </label>
              <textarea
                rows={8}
                value={answerText}
                onChange={(e) => setAnswerText(e.target.value)}
                placeholder="Paste the student's typed response or transcribed derivation steps..."
                className="w-full bg-zinc-800/80 border border-white/10 rounded-xl p-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
              />
            </div>

            <button
              type="submit"
              disabled={isEvaluating || !questionText.trim() || !answerText.trim()}
              className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold text-sm transition shadow-lg shadow-emerald-600/30 disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              {isEvaluating ? (
                <>
                  <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                  </svg>
                  <span>Auditing Step Marking...</span>
                </>
              ) : (
                <span>Evaluate Answer</span>
              )}
            </button>
          </form>
        </div>

        {/* Evaluation Output (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {!evaluation ? (
            <div className="bg-zinc-900/60 border border-dashed border-white/10 rounded-2xl p-12 text-center">
              <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center mx-auto mb-3 text-zinc-400 text-xl">
                ⚖️
              </div>
              <h3 className="text-base font-semibold text-white mb-1">Ready for CBSE Evaluation</h3>
              <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                Submit an answer on the left to receive a comprehensive breakdown of step-wise marks, missing formulas, and personalized marks-improvement tips.
              </p>
            </div>
          ) : (
            <div className="space-y-6 animate-fadeIn">
              {/* Score Summary Banner */}
              <div className="bg-gradient-to-br from-zinc-900 to-black border border-white/15 rounded-2xl p-6 shadow-xl flex items-center justify-between">
                <div>
                  <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Marks Awarded</div>
                  <div className="text-4xl font-extrabold text-white mt-1">
                    <span className="text-emerald-400">{evaluation.awarded_total}</span>
                    <span className="text-zinc-500 text-2xl font-normal"> / {evaluation.max_marks || maxMarks}</span>
                  </div>
                  <div className="text-xs text-zinc-400 mt-1">
                    Score percentage: {Math.round((evaluation.awarded_total / (evaluation.max_marks || maxMarks)) * 100)}%
                  </div>
                </div>

                <div className="text-right">
                  <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase border ${
                    evaluation.awarded_total === (evaluation.max_marks || maxMarks)
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                      : evaluation.awarded_total > (evaluation.max_marks || maxMarks) / 2
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                      : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                  }`}>
                    {evaluation.awarded_total === (evaluation.max_marks || maxMarks) ? 'Full Marks' : 'Steps Incomplete'}
                  </span>
                </div>
              </div>

              {/* Step-by-Step Breakdown */}
              <div className="bg-zinc-900/90 border border-white/10 rounded-2xl p-6 shadow-xl space-y-4">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center justify-between">
                  <span>Marking Scheme Step Audit</span>
                  <span className="text-xs text-zinc-400 font-normal">Rule: 1 mark per distinct step/point</span>
                </h3>

                <div className="space-y-3">
                  {(evaluation.step_breakdown || evaluation.steps || []).map((step, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-xl border bg-zinc-950/70 border-white/5 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-zinc-300">
                          Step {idx + 1}: {step.expected_step}
                        </span>
                        <span className={`text-xs font-bold px-2 py-0.5 rounded border ${
                          step.awarded === step.max
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                            : 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                        }`}>
                          {step.awarded} / {step.max}
                        </span>
                      </div>

                      {step.matched_evidence && (
                        <div className="text-xs text-emerald-400/90 bg-emerald-950/20 p-2 rounded-lg border border-emerald-500/10">
                          <strong>Identified:</strong> {step.matched_evidence}
                        </div>
                      )}

                      {step.missing_or_wrong && (
                        <div className="text-xs text-rose-400/90 bg-rose-950/20 p-2 rounded-lg border border-rose-500/10">
                          <strong>Deduction reason:</strong> {step.missing_or_wrong}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Actionable Marks Improvement Advice */}
              {evaluation.how_to_gain_marks && evaluation.how_to_gain_marks.length > 0 && (
                <div className="bg-zinc-900/90 border border-white/10 rounded-2xl p-6 shadow-xl space-y-3">
                  <h3 className="text-sm font-bold text-amber-300 uppercase tracking-wider flex items-center space-x-2">
                    <span>💡 How to Gain Full Marks in the Board Exam</span>
                  </h3>
                  <ul className="space-y-2">
                    {evaluation.how_to_gain_marks.map((tip, idx) => (
                      <li key={idx} className="text-xs text-zinc-300 flex items-start space-x-2">
                        <span className="text-amber-400 font-bold">•</span>
                        <span>{tip}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Model Answer */}
              {evaluation.model_answer_md && (
                <div className="bg-zinc-900/90 border border-white/10 rounded-2xl p-6 shadow-xl space-y-3">
                  <h3 className="text-sm font-bold text-zinc-200 uppercase tracking-wider">
                    Official CBSE Model Answer
                  </h3>
                  <div className="text-sm text-zinc-300 bg-zinc-950/80 p-4 rounded-xl border border-white/5 leading-relaxed">
                    <Md>{evaluation.model_answer_md}</Md>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
