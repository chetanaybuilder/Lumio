import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';

const TASK_BADGES = {
  learn: { label: 'Learn Concept', color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' },
  revise: { label: 'Revision', color: 'bg-blue-500/20 text-blue-300 border-blue-500/30' },
  drill: { label: 'Weakness Drill', color: 'bg-amber-500/20 text-amber-300 border-amber-500/30' },
  mock: { label: 'Full Mock Exam', color: 'bg-purple-500/20 text-purple-300 border-purple-500/30' }
};

export default function RoadmapView() {
  const [examTargets, setExamTargets] = useState([]);
  const [activeTarget, setActiveTarget] = useState(null);
  const [roadmapItems, setRoadmapItems] = useState([]);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [isLoading, setIsLoading] = useState(true);
  const [isConfiguring, setIsConfiguring] = useState(false);
  const [examDateInput, setExamDateInput] = useState('');
  const [dailyMinutesInput, setDailyMinutesInput] = useState(90);
  const [subjectInput, setSubjectInput] = useState('Mathematics');
  const [classLevelInput, setClassLevelInput] = useState(12);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadRoadmapData();
  }, []);

  const loadRoadmapData = async () => {
    try {
      // Load active roadmap items
      const items = await api.getRoadmap();
      setRoadmapItems(items || []);

      // Set target countdown sample if none exist
      const defaultDate = new Date();
      defaultDate.setDate(defaultDate.getDate() + 45);
      setExamDateInput(defaultDate.toISOString().split('T')[0]);
    } catch (err) {
      console.error('Failed to load roadmap:', err);
      setError('Could not load roadmap schedule.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveTarget = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await api.createExamTarget({
        class_level: parseInt(classLevelInput, 10),
        subject: subjectInput,
        exam_date: examDateInput,
        daily_minutes: parseInt(dailyMinutesInput, 10)
      });
      setActiveTarget(res);
      setIsConfiguring(false);
      // Refresh roadmap
      const items = await api.getRoadmap();
      setRoadmapItems(items || []);
    } catch (err) {
      console.error('Failed to create exam target:', err);
      setError(err.message || 'Failed to save exam target schedule.');
    }
  };

  const handleToggleTask = (itemId) => {
    setRoadmapItems((prev) =>
      prev.map((item) =>
        item.id === itemId
          ? { ...item, done_at: item.done_at ? null : new Date().toISOString() }
          : item
      )
    );
  };

  // Group items by plan_date
  const groupedItems = roadmapItems.reduce((acc, item) => {
    const d = item.plan_date || 'Today';
    if (!acc[d]) acc[d] = [];
    acc[d].push(item);
    return acc;
  }, {});

  const datesList = Object.keys(groupedItems).sort();

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Title & Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center space-x-2 text-xs text-zinc-400 mb-1">
            <Link to="/vault" className="hover:text-white transition">Vault</Link>
            <span>/</span>
            <span className="text-zinc-200">Revision Roadmap</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">
            Personalized CBSE Revision Roadmap
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Deterministic daily study planner calibrated by topic syllabus weightage, urgency curve, and mistake mastery.
          </p>
        </div>

        <button
          onClick={() => setIsConfiguring(!isConfiguring)}
          className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition shadow-lg shadow-indigo-600/30"
        >
          {isConfiguring ? 'Close Target Setup' : '⚙️ Set Exam Target Date'}
        </button>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-950/40 border border-red-500/40 rounded-xl text-xs text-red-300">
          {error}
        </div>
      )}

      {/* Target Setup Panel */}
      {isConfiguring && (
        <div className="mb-8 p-6 bg-zinc-900/90 border border-white/10 rounded-2xl shadow-xl backdrop-blur-md space-y-4">
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-indigo-500"></span>
            <span>Configure Board Exam Target & Daily Schedule</span>
          </h2>

          <form onSubmit={handleSaveTarget} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">
                Class Level
              </label>
              <select
                value={classLevelInput}
                onChange={(e) => setClassLevelInput(e.target.value)}
                className="w-full bg-zinc-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white"
              >
                <option value={10}>Class 10 CBSE</option>
                <option value={12}>Class 12 CBSE</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">
                Subject
              </label>
              <select
                value={subjectInput}
                onChange={(e) => setSubjectInput(e.target.value)}
                className="w-full bg-zinc-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white"
              >
                <option value="Mathematics">Mathematics</option>
                <option value="Physics">Physics</option>
                <option value="Chemistry">Chemistry</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">
                Board Exam Date
              </label>
              <input
                type="date"
                value={examDateInput}
                onChange={(e) => setExamDateInput(e.target.value)}
                className="w-full bg-zinc-800 border border-white/10 rounded-xl px-3 py-2 text-sm text-white"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">
                Daily Minutes: {dailyMinutesInput}m
              </label>
              <input
                type="range"
                min="30"
                max="300"
                step="15"
                value={dailyMinutesInput}
                onChange={(e) => setDailyMinutesInput(e.target.value)}
                className="w-full accent-indigo-500"
              />
            </div>

            <div className="md:col-span-4 flex justify-end">
              <button
                type="submit"
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-xs uppercase tracking-wider shadow-lg shadow-indigo-600/30"
              >
                Calculate Personalized Roadmap
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Countdown Card */}
      <div className="bg-gradient-to-r from-indigo-950/80 via-zinc-900 to-zinc-950 border border-indigo-500/20 rounded-2xl p-6 shadow-xl mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
            Active Target
          </span>
          <h2 className="text-xl font-bold text-white mt-1">CBSE Class 12 Board Examination</h2>
          <p className="text-xs text-zinc-400">Target daily study allocation: 90 minutes / day</p>
        </div>

        <div className="flex items-center space-x-6">
          <div className="text-center">
            <div className="text-3xl font-extrabold text-indigo-400 font-mono">42</div>
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold">Days Remaining</div>
          </div>
          <div className="h-10 w-px bg-white/10"></div>
          <div className="text-center">
            <div className="text-3xl font-extrabold text-emerald-400 font-mono">
              {roadmapItems.filter((i) => i.done_at).length} / {roadmapItems.length || 1}
            </div>
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold">Tasks Completed</div>
          </div>
        </div>
      </div>

      {/* Roadmap Days Schedule */}
      {isLoading ? (
        <div className="text-center py-16 text-zinc-500 text-sm">Loading roadmap timeline...</div>
      ) : roadmapItems.length === 0 ? (
        <div className="bg-zinc-900/60 border border-dashed border-white/10 rounded-2xl p-16 text-center">
          <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center mx-auto mb-3 text-zinc-400 text-xl">
            📅
          </div>
          <h3 className="text-base font-semibold text-white mb-1">No Study Roadmap Generated</h3>
          <p className="text-xs text-zinc-400 max-w-sm mx-auto mb-4">
            Click "Set Exam Target Date" above to calculate your daily revision roadmap tailored to CBSE subject weightages.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {datesList.map((dateStr) => {
            const dayItems = groupedItems[dateStr];
            const isToday = dateStr === new Date().toISOString().split('T')[0];

            return (
              <div key={dateStr} className="bg-zinc-900/80 border border-white/10 rounded-2xl p-5 shadow-lg space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-white/5">
                  <div className="flex items-center space-x-3">
                    <span className="text-sm font-bold text-white">
                      {new Date(dateStr).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}
                    </span>
                    {isToday && (
                      <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                        Today's Focus
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-zinc-400 font-mono">
                    {dayItems.reduce((sum, item) => sum + (item.est_minutes || 0), 0)} mins allocated
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {dayItems.map((item) => {
                    const badge = TASK_BADGES[item.task_type] || {
                      label: item.task_type,
                      color: 'bg-zinc-800 text-zinc-300 border-white/10'
                    };
                    const isDone = Boolean(item.done_at);

                    return (
                      <div
                        key={item.id}
                        onClick={() => handleToggleTask(item.id)}
                        className={`p-4 rounded-xl border transition cursor-pointer flex items-start space-x-3 select-none ${
                          isDone
                            ? 'bg-zinc-950/40 border-white/5 opacity-60'
                            : 'bg-zinc-800/60 border-white/10 hover:border-indigo-500/40'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isDone}
                          onChange={() => {}} // handled by parent onClick
                          className="mt-1 w-4 h-4 rounded text-indigo-600 accent-indigo-500 cursor-pointer"
                        />

                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-1">
                            <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${badge.color}`}>
                              {badge.label}
                            </span>
                            <span className="text-xs text-zinc-400 font-mono">
                              {item.est_minutes}m
                            </span>
                          </div>

                          <h4 className={`text-sm font-medium ${isDone ? 'line-through text-zinc-400' : 'text-zinc-100'}`}>
                            {item.title || item.topic_title || `Syllabus Topic Unit`}
                          </h4>

                          {item.priority_score && (
                            <div className="mt-1 text-[10px] text-zinc-500">
                              Urgency Priority: {(item.priority_score).toFixed(2)}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
