import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  FileText,
  Layers,
  Sparkles,
  ArrowLeft,
  CheckCircle2,
  Clock,
  MessageSquareCode,
  TableProperties
} from 'lucide-react';
import { request } from '../lib/api';
import StatusBadge from '../components/StatusBadge';

export function DocumentView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState(null);
  const [statusData, setStatusData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const fetchDocDetails = async () => {
    try {
      const d = await request(`/api/documents/${id}`);
      setDoc(d);
      const s = await request(`/api/documents/${id}/status`);
      setStatusData(s);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocDetails();
    // Poll every 2 seconds if status is uploading, uploaded, queued, or processing
    const interval = setInterval(() => {
      request(`/api/documents/${id}/status`)
        .then((s) => {
          setStatusData(s);
          if (s.status === 'ready' || s.status === 'failed') {
            clearInterval(interval);
          }
        })
        .catch(() => {});
    }, 2000);

    return () => clearInterval(interval);
  }, [id]);

  const handleGenerateNotes = async () => {
    setGenerating(true);
    try {
      const res = await request(`/api/documents/${id}/notes`, { method: 'POST' });
      navigate(`/notes/${res.id}`);
    } catch (err) {
      alert(`Note generation failed: ${err.message}`);
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateCheatsheet = async () => {
    setGenerating(true);
    try {
      await request(`/api/documents/${id}/cheatsheet`, { method: 'POST' });
      navigate(`/cheatsheet/${id}`);
    } catch (err) {
      alert(`Cheat sheet generation failed: ${err.message}`);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const job = statusData?.job;
  const isReady = statusData?.status === 'ready';

  return (
    <div className="flex-1 p-6 max-w-5xl mx-auto w-full">
      <Link to="/vault" className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white mb-6">
        <ArrowLeft className="w-4 h-4" />
        Back to Study Vault
      </Link>

      <div className="vault-glass rounded-3xl p-6 sm:p-8 border border-slate-800 mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="px-2.5 py-1 rounded text-xs font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                Class {doc?.class_level || 12} • {doc?.subject || 'STEM'}
              </span>
              <StatusBadge status={statusData?.status || doc?.status} />
            </div>
            <h1 className="font-display font-extrabold text-2xl sm:text-3xl text-white">{doc?.title}</h1>
            <p className="text-xs text-slate-400 mt-1">
              File: {doc?.original_filename} • {doc?.page_count ? `${doc.page_count} pages` : 'Analyzing page count'}
            </p>
          </div>
        </div>

        {/* Pipeline Stage Monitor */}
        {!isReady && (
          <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-200">
                Stage: <span className="text-indigo-400 uppercase tracking-wider">{job?.stage || 'Preparing'}</span>
              </span>
              <span className="text-xs font-bold text-indigo-300">{job?.progress_pct || 0}%</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden mb-3">
              <div
                className="bg-gradient-to-r from-indigo-500 to-purple-500 h-full transition-all duration-500"
                style={{ width: `${job?.progress_pct || 10}%` }}
              />
            </div>
            <p className="text-[11px] text-slate-400">
              PyMuPDF layout analyzer streaming in 10-page batches. Memory bounded &lt; 600MB.
            </p>
          </div>
        )}

        {/* Action Suite */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-slate-800/80">
          <button
            onClick={handleGenerateNotes}
            disabled={!isReady || generating}
            className="p-4 rounded-2xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 hover:border-indigo-500/40 text-left transition-all disabled:opacity-50"
          >
            <FileText className="w-5 h-5 text-indigo-400 mb-2" />
            <h4 className="font-semibold text-sm text-slate-100">Deep Notes AI</h4>
            <p className="text-[11px] text-slate-400 mt-1">Map-reduce concept notes with derivations.</p>
          </button>

          <button
            onClick={handleGenerateCheatsheet}
            disabled={!isReady || generating}
            className="p-4 rounded-2xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 hover:border-purple-500/40 text-left transition-all disabled:opacity-50"
          >
            <TableProperties className="w-5 h-5 text-purple-400 mb-2" />
            <h4 className="font-semibold text-sm text-slate-100">Formula Cheat Sheet</h4>
            <p className="text-[11px] text-slate-400 mt-1">Printable A4 two-column LaTeX summary.</p>
          </button>

          <Link
            to={`/tutor/${id}`}
            className="p-4 rounded-2xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 hover:border-pink-500/40 text-left transition-all block"
          >
            <MessageSquareCode className="w-5 h-5 text-pink-400 mb-2" />
            <h4 className="font-semibold text-sm text-slate-100">Socratic CBSE Tutor</h4>
            <p className="text-[11px] text-slate-400 mt-1">5-level guided discovery chat.</p>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default DocumentView;
