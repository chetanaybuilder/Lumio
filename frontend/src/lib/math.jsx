import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import 'katex/dist/contrib/mhchem.js';

export function Md({ children, className = '' }) {
  if (!children) return null;

  return (
    <div className={`prose prose-invert max-w-none math-markdown ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[
          [
            rehypeKatex,
            {
              throwOnError: false,
              errorColor: '#ef4444',
              strict: false
            }
          ]
        ]}
        components={{
          table: ({ node, ...props }) => (
            <div className="overflow-x-auto my-4 rounded-xl border border-slate-800 bg-slate-900/60 shadow-lg">
              <table className="w-full text-left text-sm text-slate-200 border-collapse" {...props} />
            </div>
          ),
          th: ({ node, ...props }) => (
            <th className="border-b border-slate-800 bg-slate-800/80 px-4 py-3 font-semibold text-indigo-300" {...props} />
          ),
          td: ({ node, ...props }) => (
            <td className="border-b border-slate-800/60 px-4 py-2.5 text-slate-300" {...props} />
          ),
          code: ({ node, inline, className, children, ...props }) => {
            if (inline) {
              return (
                <code className="bg-slate-800/80 text-amber-300 px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
                  {children}
                </code>
              );
            }
            return (
              <pre className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-slate-200 overflow-x-auto text-xs font-mono my-3">
                <code {...props}>{children}</code>
              </pre>
            );
          }
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

export default Md;
