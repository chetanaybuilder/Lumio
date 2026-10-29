import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../lib/api';
import { Md } from '../lib/math';

const HINT_BADGES = {
  0: { label: 'Clarification', color: 'bg-blue-500/20 text-blue-300 border-blue-500/30' },
  1: { label: 'Guiding Question', color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' },
  2: { label: 'Conceptual Hint', color: 'bg-amber-500/20 text-amber-300 border-amber-500/30' },
  3: { label: 'Next Step Only', color: 'bg-purple-500/20 text-purple-300 border-purple-500/30' },
  4: { label: 'Complete Solution', color: 'bg-rose-500/20 text-rose-300 border-rose-500/30' }
};

export default function TutorView() {
  const { id: sessionIdOrDocId } = useParams();
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [currentHintLevel, setCurrentHintLevel] = useState(1);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' | 'shortcuts'
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  useEffect(() => {
    // Initialize or load tutor session
    async function initSession() {
      try {
        // Create or get session
        const sess = await api.createTutorSession({
          document_id: sessionIdOrDocId && sessionIdOrDocId.length > 20 ? sessionIdOrDocId : null,
          title: 'CBSE Socratic Inquiry'
        });
        setSession(sess);
        // Initial greeting
        setMessages([
          {
            id: 'init-1',
            role: 'assistant',
            hint_level: 0,
            content: "Namaste! I am your **VexoVault Socratic CBSE Tutor**. \n\nTell me what topic or question you're tackling today—whether it's Electromagnetic Induction, Chemical Kinetics, or Calculus. I won't just dump the final answer on you; we'll break it down step-by-step so you master the CBSE marking scheme!"
          }
        ]);
      } catch (err) {
        console.error('Failed to init tutor session:', err);
        setError('Could not connect to the Socratic Tutor service. Ensure backend is active.');
      }
    }
    initSession();
  }, [sessionIdOrDocId]);

  const handleSendMessage = async (e) => {
    e?.preventDefault();
    if (!inputMessage.trim() || isStreaming || !session) return;

    const userText = inputMessage.trim();
    setInputMessage('');
    setError(null);

    const newUserMsg = {
      id: `usr-${Date.now()}`,
      role: 'user',
      content: userText
    };

    setMessages((prev) => [...prev, newUserMsg]);
    setIsStreaming(true);
    setStreamingContent('');

    try {
      let accumulatedText = '';
      let finalHint = currentHintLevel;

      await api.streamTutorMessage(
        session.id,
        userText,
        currentHintLevel,
        (token) => {
          accumulatedText += token;
          setStreamingContent(accumulatedText);
        },
        (doneData) => {
          setIsStreaming(false);
          setStreamingContent('');
          if (doneData.hint_level !== undefined) {
            finalHint = doneData.hint_level;
            setCurrentHintLevel(doneData.hint_level);
          }
          setMessages((prev) => [
            ...prev,
            {
              id: `asst-${Date.now()}`,
              role: 'assistant',
              hint_level: finalHint,
              content: accumulatedText
            }
          ]);
        },
        (errMsg) => {
          setIsStreaming(false);
          setStreamingContent('');
          setError(errMsg);
        }
      );
    } catch (err) {
      setIsStreaming(false);
      setStreamingContent('');
      setError(err.message || 'Error communicating with Socratic AI.');
    }
  };

  const sendQuickPrompt = (promptText) => {
    setInputMessage(promptText);
  };

  const advanceHintManually = () => {
    const nextLevel = Math.min(4, currentHintLevel + 1);
    setCurrentHintLevel(nextLevel);
    setInputMessage("I am stuck on this step. Could you give me the next hint?");
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-6xl mx-auto px-4 py-4">
      {/* Header Bar */}
      <div className="flex items-center justify-between pb-4 border-b border-white/10 bg-black/40 backdrop-blur-md px-4 py-3 rounded-t-2xl">
        <div className="flex items-center space-x-3">
          <Link to="/vault" className="text-zinc-400 hover:text-white transition">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </Link>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-white tracking-wide">Socratic CBSE Tutor</h1>
              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                Active Session
              </span>
            </div>
            <p className="text-xs text-zinc-400">Class 10-12 Curriculum Aligned • Real-time Math & Chemistry Rendering</p>
          </div>
        </div>

        {/* Current Hint Level Indicator */}
        <div className="flex items-center space-x-3">
          <div className="text-right hidden sm:block">
            <div className="text-xs text-zinc-400">Guidance Level</div>
            <div className="text-xs font-semibold text-zinc-200">
              Level {currentHintLevel} / 4 ({HINT_BADGES[currentHintLevel]?.label})
            </div>
          </div>
          <button
            onClick={advanceHintManually}
            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-600/50 transition font-medium"
            title="Ask for a higher hint level"
          >
            I'm Stuck (Next Hint)
          </button>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-zinc-950/60 border-x border-white/5">
        {error && (
          <div className="p-3 bg-red-950/40 border border-red-500/40 rounded-xl text-red-300 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-xs underline text-red-400">Dismiss</button>
          </div>
        )}

        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          const hintBadge = msg.hint_level !== undefined ? HINT_BADGES[msg.hint_level] : null;

          return (
            <div
              key={msg.id}
              className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
            >
              <div className="flex items-center space-x-2 mb-1 px-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                  {isUser ? 'You' : 'VexoVault Tutor'}
                </span>
                {!isUser && hintBadge && (
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border ${hintBadge.color}`}>
                    {hintBadge.label}
                  </span>
                )}
              </div>

              <div
                className={`max-w-[85%] rounded-2xl p-4 shadow-lg leading-relaxed ${
                  isUser
                    ? 'bg-gradient-to-r from-indigo-600 to-indigo-700 text-white rounded-tr-none'
                    : 'bg-zinc-900/90 border border-white/10 text-zinc-200 rounded-tl-none'
                }`}
              >
                <Md>{msg.content}</Md>
              </div>
            </div>
          );
        })}

        {/* Live Streaming Assistant Output */}
        {isStreaming && (
          <div className="flex flex-col items-start">
            <div className="flex items-center space-x-2 mb-1 px-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                VexoVault Tutor
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full border bg-amber-500/20 text-amber-300 border-amber-500/30 animate-pulse">
                Reasoning...
              </span>
            </div>
            <div className="max-w-[85%] rounded-2xl rounded-tl-none p-4 shadow-lg bg-zinc-900/90 border border-white/10 text-zinc-200">
              <Md>{streamingContent || '...'}</Md>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts Carousel */}
      <div className="bg-black/50 border-x border-t border-white/5 px-4 py-2 flex items-center space-x-2 overflow-x-auto text-xs">
        <span className="text-zinc-500 whitespace-nowrap">Suggested:</span>
        <button
          onClick={() => sendQuickPrompt("Explain Lenz's law with the Delhi Metro or a real-life analogy.")}
          className="px-2.5 py-1 rounded-full bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 border border-white/5 whitespace-nowrap transition"
        >
          Lenz's Law Analogy
        </button>
        <button
          onClick={() => sendQuickPrompt("How do I derive the integrated rate law for a first-order reaction?")}
          className="px-2.5 py-1 rounded-full bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 border border-white/5 whitespace-nowrap transition"
        >
          1st Order Rate Derivation
        </button>
        <button
          onClick={() => sendQuickPrompt("What are the key points for finding extreme values using second derivatives?")}
          className="px-2.5 py-1 rounded-full bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 border border-white/5 whitespace-nowrap transition"
        >
          Max-Min Steps
        </button>
        <button
          onClick={() => sendQuickPrompt("Give me a practice problem on Raoult's Law with vapor pressures.")}
          className="px-2.5 py-1 rounded-full bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 border border-white/5 whitespace-nowrap transition"
        >
          Raoult's Law Practice
        </button>
      </div>

      {/* Input Box Footer */}
      <div className="p-4 bg-black/60 backdrop-blur-md rounded-b-2xl border border-white/10">
        <form onSubmit={handleSendMessage} className="flex items-center space-x-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={isStreaming}
            placeholder="Type your doubt, answer, or equation (e.g. \int x^2 dx or $E = mc^2$)..."
            className="flex-1 bg-zinc-900/90 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            type="submit"
            disabled={isStreaming || !inputMessage.trim()}
            className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition flex items-center space-x-2 shadow-lg shadow-indigo-600/30"
          >
            {isStreaming ? (
              <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
              </svg>
            ) : (
              <span>Send</span>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
