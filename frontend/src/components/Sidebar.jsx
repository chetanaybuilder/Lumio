import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  FolderKanban,
  Layers,
  FileCheck2,
  BrainCircuit,
  AlertTriangle,
  CalendarCheck2,
  MessageSquareCode
} from 'lucide-react';

const navItems = [
  { to: '/vault', label: 'Study Vault', icon: FolderKanban, desc: 'Textbooks & notes' },
  { to: '/tutor/live', label: 'Socratic Tutor', icon: MessageSquareCode, desc: 'CBSE AI inquiry' },
  { to: '/flashcards', label: 'Spaced Recall', icon: Layers, desc: 'SM-2 flashcard decks' },
  { to: '/paper', label: 'Board Mocks', icon: FileCheck2, desc: 'CBSE Sec A-E papers' },
  { to: '/evaluate', label: 'Marks AI', icon: BrainCircuit, desc: 'Marking scheme audit' },
  { to: '/mistakes', label: 'Mistake Vault', icon: AlertTriangle, desc: 'Weakness drills' },
  { to: '/roadmap', label: 'Revision Plan', icon: CalendarCheck2, desc: 'Daily target scheduler' },
];

export function Sidebar() {
  return (
    <aside className="w-64 border-r border-slate-800 bg-[#090d16]/50 p-4 hidden md:flex flex-col gap-2 shrink-0">
      <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
        Mastery Modules
      </div>
      <nav className="flex flex-col gap-1.5">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-gradient-to-r from-indigo-600/20 to-purple-600/10 text-indigo-300 border border-indigo-500/30 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border border-transparent'
                }`
              }
            >
              <Icon className="w-4 h-4 text-indigo-400" />
              <div>
                <p className="font-semibold text-slate-200 leading-tight">{item.label}</p>
                <p className="text-[10px] text-slate-500 leading-tight">{item.desc}</p>
              </div>
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}

export default Sidebar;
