import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Shield,
  Sparkles,
  BookOpen,
  Brain,
  CheckCircle2,
  FileCheck2,
  Layers,
  ArrowRight,
  TrendingUp,
  Cpu,
  LogIn
} from 'lucide-react';
import { request } from '../lib/api';

export function Landing({ user, setUser }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const googleBtnRef = useRef(null);

  const handleGoogleCredentialResponse = async (response) => {
    if (!response || !response.credential) return;
    setLoading(true);
    setError(null);
    try {
      const userData = await request('/auth/google', {
        method: 'POST',
        body: JSON.stringify({ credential: response.credential })
      });
      if (setUser) setUser(userData);
      navigate('/vault');
    } catch (err) {
      setError(err.message || 'Google sign-in failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

    const renderGoogleBtn = () => {
      if (window.google?.accounts?.id && googleBtnRef.current) {
        try {
          window.google.accounts.id.initialize({
            client_id: clientId,
            callback: handleGoogleCredentialResponse,
            auto_select: false,
            cancel_on_tap_outside: true
          });

          window.google.accounts.id.renderButton(googleBtnRef.current, {
            theme: 'filled_black',
            size: 'large',
            shape: 'pill',
            text: 'continue_with',
            width: 280,
            logo_alignment: 'left'
          });
        } catch (e) {
          console.warn('Google GSI render error:', e);
        }
      }
    };

    if (window.google?.accounts?.id) {
      renderGoogleBtn();
    } else {
      const timer = setInterval(() => {
        if (window.google?.accounts?.id) {
          clearInterval(timer);
          renderGoogleBtn();
        }
      }, 250);
      return () => clearInterval(timer);
    }
  }, []);

  const handleDemoLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const userData = await request('/test/login', { method: 'POST' });
      if (setUser) setUser(userData);
      navigate('/vault');
    } catch (err) {
      setError(err.message || 'Demo login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-[calc(100vh-4rem)] flex flex-col justify-between overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-gradient-to-tr from-indigo-600/20 via-purple-600/20 to-pink-500/10 rounded-full blur-[120px] pointer-events-none" />

      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 flex-1 flex flex-col items-center justify-center text-center relative z-10">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-800/80 border border-slate-700/80 text-xs font-semibold text-indigo-300 mb-8 backdrop-blur-md shadow-inner">
          <Sparkles className="w-4 h-4 text-pink-400" />
          <span>VexoVault Architecture 2.0 • CBSE Class 9–12 & STEM</span>
        </div>

        <h1 className="font-display font-extrabold text-4xl sm:text-6xl lg:text-7xl tracking-tight text-white max-w-4xl leading-[1.1] mb-6">
          Transform Textbooks into <span className="vault-gradient-text">Board Exam Mastery.</span>
        </h1>

        <p className="max-w-2xl text-slate-300 text-base sm:text-lg mb-10 leading-relaxed font-normal">
          Direct 50MB PDF ingestion, Socratic CBSE AI tutoring with Indian analogies, official 80-mark blueprint mock papers, and active-recall flashcards with zero guesswork.
        </p>

        {error && (
          <div className="mb-6 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs max-w-md w-full">
            {error}
          </div>
        )}

        <div className="flex flex-col items-center gap-4 w-full justify-center max-w-md">
          {/* Google Sign-In Container */}
          <div className="flex flex-col items-center justify-center min-h-[44px]">
            <div ref={googleBtnRef} className="shadow-lg rounded-full" />
          </div>

          <div className="flex items-center gap-3 w-full my-1">
            <div className="flex-1 h-px bg-slate-800" />
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">or test with</span>
            <div className="flex-1 h-px bg-slate-800" />
          </div>

          <button
            onClick={handleDemoLogin}
            disabled={loading}
            className="w-full px-6 py-3 rounded-2xl bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold text-sm shadow-md transition-all hover:scale-[1.01] flex items-center justify-center gap-2"
          >
            {loading ? (
              <span>Authenticating...</span>
            ) : (
              <>
                <LogIn className="w-4 h-4 text-indigo-400" />
                <span>One-Click Demo Student (Alex Mercer)</span>
              </>
            )}
          </button>
        </div>

        <p className="text-[11px] text-slate-500 mt-3">
          OAuth 2.0 with PostgreSQL HttpOnly cookies • Pre-seeded CBSE curriculum ready
        </p>

        {/* Feature Highlights Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16 w-full text-left">
          <div className="vault-glass rounded-2xl p-6 border border-slate-800 hover:border-indigo-500/30 transition-all">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center text-indigo-400 mb-4 border border-indigo-500/20">
              <Brain className="w-5 h-5" />
            </div>
            <h3 className="font-display font-bold text-slate-100 text-base mb-2">Socratic CBSE Tutor</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              5-stage hint state machine (Clarify → Guiding question → Conceptual hint with Indian analogies → Next step → Worked solution).
            </p>
          </div>

          <div className="vault-glass rounded-2xl p-6 border border-slate-800 hover:border-purple-500/30 transition-all">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-400 mb-4 border border-purple-500/20">
              <FileCheck2 className="w-5 h-5" />
            </div>
            <h3 className="font-display font-bold text-slate-100 text-base mb-2">Official 80-Mark Mocks</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Full CBSE Sections A through E generation strictly compliant with current official sample paper blueprints and marking schemes.
            </p>
          </div>

          <div className="vault-glass rounded-2xl p-6 border border-slate-800 hover:border-pink-500/30 transition-all">
            <div className="w-10 h-10 rounded-xl bg-pink-500/10 flex items-center justify-center text-pink-400 mb-4 border border-pink-500/20">
              <Layers className="w-5 h-5" />
            </div>
            <h3 className="font-display font-bold text-slate-100 text-base mb-2">SM-2 Spaced Recall</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Active recall flashcard decks with mathematical formulas in KaTeX and SuperMemo-2 interval scheduling.
            </p>
          </div>
        </div>
      </main>

      <footer className="border-t border-slate-900/60 py-6 text-center text-xs text-slate-500">
        VexoVault (v2) • Built strictly according to the Architecture & Implementation Blueprint • React 18, FastAPI, pgvector & Gemini
      </footer>
    </div>
  );
}

export default Landing;
