import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Printer, ArrowLeft, TableProperties, Sparkles } from 'lucide-react';
import { request } from '../lib/api';
import Md from '../lib/math';

export function CheatSheetView() {
  const { id } = useParams();
  const [cs, setCs] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    request(`/api/documents/${id}/cheatsheet`)
      .then((data) => setCs(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!cs) {
    return (
      <div className="flex-1 p-8 text-center text-slate-400">
        <p>Cheat sheet not generated yet.</p>
        <Link to={`/doc/${id}`} className="text-indigo-400 hover:underline mt-2 inline-block">Return to Document</Link>
      </div>
    );
  }

  return (
    <div className="flex-1 p-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between gap-4 mb-6 no-print">
        <Link to={`/doc/${id}`} className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-white">
          <ArrowLeft className="w-4 h-4" />
          Back to Document
        </Link>
        <button
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-md shadow-purple-600/20"
        >
          <Printer className="w-4 h-4" />
          Print A4 Formula Sheet
        </button>
      </div>

      <article className="vault-glass rounded-3xl p-8 sm:p-10 border border-slate-800 print-sheet">
        <Md>{cs.content_md}</Md>
      </article>
    </div>
  );
}

export default CheatSheetView;
