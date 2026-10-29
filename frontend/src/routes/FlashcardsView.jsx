import React, { useState, useEffect } from 'react';
import { Layers, RotateCcw, Check, ArrowRight, Sparkles, BookOpen } from 'lucide-react';
import { request } from '../lib/api';
import Md from '../lib/math';

export function FlashcardsView() {
  const [cards, setCards] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);

  const fetchDueCards = async () => {
    try {
      const data = await request('/api/flashcards/due');
      setCards(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDueCards();
  }, []);

  const handleReview = async (quality) => {
    if (!currentCard || reviewing) return;
    setReviewing(true);

    try {
      await request(`/api/flashcards/${currentCard.id}/review`, {
        method: 'POST',
        body: JSON.stringify({ quality })
      });

      setFlipped(false);
      setCurrentIndex((prev) => prev + 1);
    } catch (err) {
      alert(`Review error: ${err.message}`);
    } finally {
      setReviewing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const currentCard = cards[currentIndex];

  return (
    <div className="flex-1 p-6 max-w-4xl mx-auto w-full flex flex-col items-center">
      <div className="w-full flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display font-extrabold text-2xl sm:text-3xl text-white">
            Spaced <span className="vault-gradient-text">Recall</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">SuperMemo-2 (SM-2) adaptive retention algorithm.</p>
        </div>
        <div className="px-3 py-1.5 rounded-xl bg-slate-800 border border-slate-700 text-xs font-semibold text-indigo-300">
          {cards.length > 0 ? `${currentIndex + 1} of ${cards.length} Due` : '0 Due'}
        </div>
      </div>

      {cards.length === 0 || currentIndex >= cards.length ? (
        <div className="vault-glass rounded-3xl p-12 border border-slate-800 text-center max-w-md w-full">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center mx-auto mb-4 border border-emerald-500/20">
            <Check className="w-6 h-6" />
          </div>
          <h3 className="font-display font-bold text-lg text-white mb-1">All Caught Up!</h3>
          <p className="text-xs text-slate-400 mb-6">
            You've completed all active recall flashcards due for review today. Great work!
          </p>
          <button
            onClick={() => {
              setCurrentIndex(0);
              fetchDueCards();
            }}
            className="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-slate-700"
          >
            Refresh Due Queue
          </button>
        </div>
      ) : (
        <div className="w-full max-w-2xl flex flex-col items-center">
          {/* Card Frame */}
          <div
            onClick={() => setFlipped(!flipped)}
            className="w-full min-h-[320px] vault-glass rounded-3xl p-8 border border-slate-700/80 cursor-pointer transition-all hover:border-indigo-500/50 flex flex-col justify-between shadow-2xl relative group"
          >
            <div className="flex items-center justify-between text-[11px] text-slate-400 mb-4">
              <span className="uppercase tracking-wider font-semibold text-indigo-400">
                {flipped ? 'Answer & Explanation' : 'Question / Concept Prompt'}
              </span>
              <span className="text-slate-500 text-[10px]">Click to flip card</span>
            </div>

            <div className="flex-1 flex items-center justify-center text-center my-4">
              <div className="text-base sm:text-lg text-slate-100 font-medium">
                {flipped ? (
                  <Md>{currentCard.back}</Md>
                ) : (
                  <Md>{currentCard.front}</Md>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between text-[10px] text-slate-500 pt-4 border-t border-slate-800/80">
              <span>Interval: {currentCard.interval_days || 0}d</span>
              <span>Ease: {Number(currentCard.ease_factor || 2.5).toFixed(2)}</span>
            </div>
          </div>

          {/* SM-2 Rating Controls */}
          {flipped ? (
            <div className="w-full mt-6 flex flex-col gap-2">
              <p className="text-[11px] text-center text-slate-400 font-medium">Rate your recall quality:</p>
              <div className="grid grid-cols-6 gap-2">
                {[
                  { q: 0, label: '0: Blackout', color: 'bg-rose-950/60 border-rose-800/80 text-rose-300' },
                  { q: 1, label: '1: Fail', color: 'bg-rose-900/40 border-rose-700/60 text-rose-200' },
                  { q: 2, label: '2: Hard', color: 'bg-amber-950/60 border-amber-800/80 text-amber-300' },
                  { q: 3, label: '3: Good', color: 'bg-indigo-950/60 border-indigo-800/80 text-indigo-300' },
                  { q: 4, label: '4: Easy', color: 'bg-emerald-950/60 border-emerald-800/80 text-emerald-300' },
                  { q: 5, label: '5: Perfect', color: 'bg-emerald-900/60 border-emerald-700 text-emerald-200' }
                ].map((btn) => (
                  <button
                    key={btn.q}
                    disabled={reviewing}
                    onClick={() => handleReview(btn.q)}
                    className={`py-2 px-1 rounded-xl border text-[10px] sm:text-xs font-semibold text-center transition-all hover:scale-105 ${btn.color}`}
                  >
                    {btn.label}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <button
              onClick={() => setFlipped(true)}
              className="mt-6 px-6 py-2.5 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20"
            >
              Reveal Answer
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default FlashcardsView;
