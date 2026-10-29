import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  BookOpen,
  FileText,
  Layers,
  Sparkles,
  AlertCircle,
  Clock,
  ArrowRight,
  Flame,
  CheckCircle2,
  ChevronRight
} from 'lucide-react';
import { request } from '../lib/api';
import StatusBadge from '../components/StatusBadge';

export function Vault() {
  const navigate = useNavigate();
  const [vaultData, setVaultData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadSubject, setUploadSubject] = useState('Mathematics');
  const [uploadClass, setUploadClass] = useState(12);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);

  const fetchVault = async () => {
    try {
      const data = await request('/api/vault');
      setVaultData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVault();
  }, []);

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!uploadFile) return;

    setUploading(true);
    setUploadProgress(10);
    try {
      // 1. Initialize Upload
      const initRes = await request('/api/uploads/init', {
        method: 'POST',
        body: JSON.stringify({
          filename: uploadFile.name,
          size_bytes: uploadFile.size,
          subject: uploadSubject,
          class_level: Number(uploadClass)
        })
      });

      setUploadProgress(40);

      // 2. Simulate parallel chunked multipart PUT parts
      const parts = initRes.parts.map(p => ({
        part_number: p.part_number,
        etag: `etag-${Math.random().toString(36).substring(2)}`
      }));

      setUploadProgress(70);

      // 3. Complete Upload
      const completeRes = await request('/api/uploads/complete', {
        method: 'POST',
        body: JSON.stringify({
          document_id: initRes.document_id,
          upload_id: initRes.upload_id,
          parts: parts
        })
      });

      setUploadProgress(100);
      setShowUploadModal(false);
      setUploadFile(null);
      // Navigate to document status screen
      navigate(`/doc/${initRes.document_id}`);
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-slate-400">Loading your Study Vault...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 p-6 max-w-7xl mx-auto w-full">
      {/* Top Welcome Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="font-display font-extrabold text-2xl sm:text-3xl text-white">
            Study <span className="vault-gradient-text">Vault</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Official CBSE syllabus materials, active roadmaps, and grounded STEM textbooks.
          </p>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 transition-all hover:scale-[1.02]"
        >
          <UploadCloud className="w-4 h-4" />
          Upload Textbook PDF
        </button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="vault-glass rounded-2xl p-5 border border-slate-800">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-slate-400 font-medium">Textbooks Loaded</span>
            <BookOpen className="w-4 h-4 text-indigo-400" />
          </div>
          <p className="text-2xl font-bold font-display text-white">{vaultData?.documents?.length || 0}</p>
          <p className="text-[11px] text-slate-500 mt-1">Grounded for CBSE board exams</p>
        </div>

        <div className="vault-glass rounded-2xl p-5 border border-slate-800">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-slate-400 font-medium">Deep Notes Generated</span>
            <FileText className="w-4 h-4 text-purple-400" />
          </div>
          <p className="text-2xl font-bold font-display text-white">{vaultData?.notes?.length || 0}</p>
          <p className="text-[11px] text-slate-500 mt-1">KaTeX formulas & derivations</p>
        </div>

        <div className="vault-glass rounded-2xl p-5 border border-slate-800">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-slate-400 font-medium">Unresolved Mistakes</span>
            <Flame className="w-4 h-4 text-rose-400" />
          </div>
          <p className="text-2xl font-bold font-display text-white">{vaultData?.unresolved_mistakes || 0}</p>
          <Link to="/mistakes" className="text-[11px] text-rose-400 hover:underline mt-1 inline-block">
            Launch micro-drills →
          </Link>
        </div>
      </div>

      {/* Textbooks Section */}
      <div className="mb-10">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display font-bold text-lg text-slate-100 flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-indigo-400" />
            Your Ingested Textbooks
          </h2>
        </div>

        {vaultData?.documents?.length === 0 ? (
          <div className="vault-glass rounded-2xl p-10 border border-slate-800 text-center">
            <UploadCloud className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <h3 className="text-sm font-semibold text-slate-300">No textbooks uploaded yet</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 mb-4">
              Upload any Class 10–12 NCERT or reference PDF (up to 50MB) to start generating study notes and mocks.
            </p>
            <button
              onClick={() => setShowUploadModal(true)}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 text-xs font-semibold border border-indigo-500/30"
            >
              Upload Sample PDF
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {vaultData.documents.map((doc) => (
              <div
                key={doc.id}
                className="vault-glass vault-glass-hover rounded-2xl p-5 border border-slate-800 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                      Class {doc.class_level || 12} • {doc.subject || 'STEM'}
                    </span>
                    <StatusBadge status={doc.status} />
                  </div>
                  <h3 className="font-display font-bold text-slate-100 text-base mb-1 line-clamp-1">{doc.title}</h3>
                  <p className="text-xs text-slate-400 mb-4">{doc.page_count ? `${doc.page_count} pages` : 'Analyzing pages...'}</p>
                </div>

                <div className="flex items-center gap-2 pt-3 border-t border-slate-800/80">
                  <Link
                    to={`/doc/${doc.id}`}
                    className="flex-1 py-1.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium text-center transition-colors"
                  >
                    Details & Status
                  </Link>
                  <Link
                    to={`/tutor/${doc.id}`}
                    className="py-1.5 px-3 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 text-xs font-semibold border border-indigo-500/30 transition-colors"
                  >
                    AI Tutor
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="vault-glass rounded-3xl max-w-md w-full p-6 border border-slate-700 shadow-2xl relative">
            <h3 className="font-display font-bold text-xl text-white mb-2">Upload Textbook PDF</h3>
            <p className="text-xs text-slate-400 mb-6">
              Maximum file size: 50MB. PyMuPDF extracts structure, formulas, and diagrams in 10-page batches.
            </p>

            <form onSubmit={handleUploadSubmit} className="flex flex-col gap-4">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Select PDF File</label>
                <input
                  type="file"
                  accept="application/pdf"
                  required
                  onChange={(e) => setUploadFile(e.target.files[0])}
                  className="w-full text-xs text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-500 cursor-pointer bg-slate-900 border border-slate-800 rounded-xl p-2"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Class Level</label>
                  <select
                    value={uploadClass}
                    onChange={(e) => setUploadClass(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl p-2.5 text-xs text-slate-200"
                  >
                    <option value={10}>Class 10</option>
                    <option value={12}>Class 12</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Subject</label>
                  <select
                    value={uploadSubject}
                    onChange={(e) => setUploadSubject(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl p-2.5 text-xs text-slate-200"
                  >
                    <option value="Mathematics">Mathematics</option>
                    <option value="Physics">Physics</option>
                    <option value="Chemistry">Chemistry</option>
                  </select>
                </div>
              </div>

              {uploading && (
                <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden mt-2">
                  <div
                    className="bg-indigo-500 h-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              )}

              <div className="flex items-center justify-end gap-3 mt-4">
                <button
                  type="button"
                  disabled={uploading}
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading || !uploadFile}
                  className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/30 disabled:opacity-50"
                >
                  {uploading ? `Uploading (${uploadProgress}%)...` : 'Start Ingestion'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default Vault;
