import React, { Suspense, lazy, useState, useEffect, createContext, useContext } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import { api } from './lib/api';

// React.lazy route definitions
const Landing = lazy(() => import('./routes/Landing'));
const Vault = lazy(() => import('./routes/Vault'));
const DocumentView = lazy(() => import('./routes/DocumentView'));
const NotesView = lazy(() => import('./routes/NotesView'));
const FlashcardsView = lazy(() => import('./routes/FlashcardsView'));
const CheatSheetView = lazy(() => import('./routes/CheatSheetView'));
const TutorView = lazy(() => import('./routes/TutorView'));
const PaperView = lazy(() => import('./routes/PaperView'));
const AttemptView = lazy(() => import('./routes/AttemptView'));
const EvaluateView = lazy(() => import('./routes/EvaluateView'));
const MistakesView = lazy(() => import('./routes/MistakesView'));
const RoadmapView = lazy(() => import('./routes/RoadmapView'));

export const AuthContext = createContext({
  user: null,
  setUser: () => {},
  isLoadingUser: true,
  refreshUser: async () => {}
});

export const useAuth = () => useContext(AuthContext);

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <div className="relative w-12 h-12">
        <div className="w-12 h-12 rounded-full border-2 border-indigo-500/20 border-t-indigo-500 animate-spin"></div>
        <div className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-indigo-400">
          VV
        </div>
      </div>
    </div>
  );
}

function Layout({ children, user, setUser }) {
  const location = useLocation();
  const isLanding = location.pathname === '/';

  return (
    <div className="min-h-screen bg-[#07090e] text-slate-100 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      <Navbar user={user} setUser={setUser} />
      <div className="flex-1 flex overflow-hidden">
        {user && !isLanding && <Sidebar />}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [isLoadingUser, setIsLoadingUser] = useState(true);

  const fetchCurrentUser = async () => {
    try {
      const u = await api.getCurrentUser();
      setUser(u);
    } catch (_) {
      setUser(null);
    } finally {
      setIsLoadingUser(false);
    }
  };

  useEffect(() => {
    fetchCurrentUser();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        setUser,
        isLoadingUser,
        refreshUser: fetchCurrentUser
      }}
    >
      <BrowserRouter>
        <Layout user={user} setUser={setUser}>
          <Suspense fallback={<LoadingSpinner />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/vault" element={<Vault />} />
              <Route path="/doc/:id" element={<DocumentView />} />
              <Route path="/notes/:id" element={<NotesView />} />
              <Route path="/flashcards" element={<FlashcardsView />} />
              <Route path="/cheatsheet/:id" element={<CheatSheetView />} />
              <Route path="/tutor/:id" element={<TutorView />} />
              <Route path="/paper" element={<PaperView />} />
              <Route path="/attempt/:id" element={<AttemptView />} />
              <Route path="/evaluate" element={<EvaluateView />} />
              <Route path="/mistakes" element={<MistakesView />} />
              <Route path="/roadmap" element={<RoadmapView />} />
              {/* Fallback route */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </Layout>
      </BrowserRouter>
    </AuthContext.Provider>
  );
}
