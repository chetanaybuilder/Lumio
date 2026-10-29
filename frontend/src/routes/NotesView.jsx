import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  FileText,
  Layers,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  PieChart,
  Printer
} from 'lucide-react';
import { request } from '../lib/api';
import Md from '../lib/math';

export function NotesView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [note, setNote] = useState(null);
  const [coverage, setCoverage] = useState(null);
  const [activeTab, setActiveTab] = useState('notes'); // 'notes' or 'coverage'
  const [loading, setLoading] = useState(true);
  const [generatingCards, setGeneratingCards] = useState(false);
  const [checkingCoverage, setCheckingCoverage] = useState(false);

  useEffect(() => {
    request(`/api/notes/${id}`)
      .then((n) => setNote(n))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [id]);

  const handleGenerateCards = async () => {
    setGeneratingCards(true);
    try {
      await request(`/api/notes/${id}/flashcards`, { method: 'POST' });
      navigate('/flashcards');
    } catch (err) {
      alert(`Flashcards generation failed: ${err.message}`);
    } finally {
      setGeneratingCards(false);
    }
  };

  const handleRunCoverageCheck = async () => {
    setCheckingCoverage(true);
    try {
      const rep = await request(`/api/notes/${id}/coverage`, { method: 'POST' });
      setCoverage(rep);
      setActiveTab('coverage');
    } catch (err) {
      alert(`Coverage check failed: ${err.message}`);
    } finally {
      setCheckingCoverage(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!note) {
    return (
      <div className="flex-1 p-8 text-center text-slate-400">
        <p>Study note not found.</p>
        <Link to="/vault" className="text-indigo-400 hover:underline mt-2 inline-block">Return to Vault</Link>
      </div>
    );
  }

  return (
    <div className="flex-1 p-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between gap-4 mb-6">
        <Link to="/vault" className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white">
          <ArrowLeft className="w-4 h-4" />
          Back to Study Vault
        </Link>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRunCoverageCheck}
            disabled={checkingCoverage}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-slate-700"
          >
            <PieChart className="w-3.5 h-3.5 text-purple-400" />
            {checkingCoverage ? 'Auditing...' : 'Check CBSE Coverage'}
          </button>
          <button
            onClick={handleGenerateCards}
            disabled={generatingCards}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md shadow-indigo-600/20"
          >
            <Layers className="w-3.5 h-3.5" />
            {generatingCards ? 'Generating...' : 'Create Flashcards'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 mb-6">
        <button
          onClick={() => setActiveTab('notes')}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === 'notes'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Comprehensive Notes
        </button>
        <button
          onClick={() => setActiveTab('coverage')}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === 'coverage'
              ? 'border-purple-500 text-purple-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Syllabus Coverage Audit
          {coverage && (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-purple-500/20 text-purple-300">
              {coverage.score}%
            </span>
          )}
        </button>
      </div>

      {activeTab === 'notes' ? (
        <article className="vault-glass rounded-3xl p-6 sm:p-10 border border-slate-800">
          <Md>{note.content_md}</Md>
        </article>
      ) : (
        <div className="vault-glass rounded-3xl p-6 sm:p-8 border border-slate-800">
          {coverage ? (
            <div>
              <div className="flex items-center justify-between mb-6 pb-6 border-b border-slate-800">
                <div>
                  <h3 className="font-display font-bold text-xl text-white">CBSE Curriculum Coverage</h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Audited {coverage.total_topics} leaf topics against official current-year CBSE syllabus.
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-3xl font-extrabold font-display text-purple-400">{coverage.score}%</span>
                  <p className="text-[10px] uppercase tracking-wider text-slate-500">Coverage Score</p>
                </div>
              </div>

              {coverage.missing_topics && coverage.missing_topics.length > 0 ? (
                <div>
                  <h4 className="text-xs font-semibold text-rose-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4" />
                    Missing Syllabus Topics Detected ({coverage.missing_topics.length})
                  </h4>
                  <div className="space-y-2 mb-6">
                    {coverage.missing_topics.map((t, idx) => (
                      <div key={idx} className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
                        <span className="text-xs text-slate-200">{t.title}</span>
                        <span className="text-[10px] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                          {t.weightage_marks} Marks
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  Full coverage! All audited syllabus topics are represented in these study notes.
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-10">
              <p className="text-xs text-slate-400 mb-4">Click below to audit coverage against official CBSE syllabus topics.</p>
              <button
                onClick={handleRunCoverageCheck}
                disabled={checkingCoverage}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold"
              >
                {checkingCoverage ? 'Auditing Topics...' : 'Run Coverage Checker'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default NotesView;
