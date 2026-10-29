import React from 'react';

export function StatusBadge({ status }) {
  const s = (status || '').toLowerCase();

  let styles = 'bg-slate-800 text-slate-300 border-slate-700';
  let label = status;

  if (s === 'ready' || s === 'succeeded' || s === 'evaluated') {
    styles = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    label = 'Ready';
  } else if (s === 'processing' || s === 'running' || s === 'in_progress') {
    styles = 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30 animate-pulse';
    label = 'Processing';
  } else if (s === 'queued' || s === 'uploading' || s === 'uploaded') {
    styles = 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    label = 'Queued';
  } else if (s === 'failed' || s === 'dead') {
    styles = 'bg-rose-500/10 text-rose-400 border-rose-500/30';
    label = 'Failed';
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${styles}`}>
      {label}
    </span>
  );
}

export default StatusBadge;
