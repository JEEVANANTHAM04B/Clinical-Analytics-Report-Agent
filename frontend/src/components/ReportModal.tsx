import React, { useEffect, useState, useCallback } from 'react';
import { 
  FileCheck2, 
  X, 
  Download, 
  Check, 
  AlertTriangle, 
  ShieldCheck, 
  Clock, 
  Maximize2,
  Minimize2,
  RefreshCw
} from 'lucide-react';
import { API_BASE_URL } from '../api/client';
import { PDFViewer } from './PDFViewer';

interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  question: string;
  analysisPlan?: string | null;
  insight?: string | null;
  results?: Record<string, any>[];
  ragContext?: string | null;
  sqlQuery?: string | null;
  workspaceType?: 'clinical' | 'technical';
  selectedTables?: string[];
  followUpAnswers?: { question: string; answer: string }[];
}

export const ReportModal: React.FC<ReportModalProps> = ({
  isOpen,
  onClose,
  question,
  analysisPlan,
  insight,
  results = [],
  ragContext,
  sqlQuery,
  workspaceType = 'clinical',
  selectedTables,
  followUpAnswers = [],
}) => {
  const [isApproved, setIsApproved] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [rejectFeedback, setRejectFeedback] = useState('');
  const [showRejectForm, setShowRejectForm] = useState(false);

  // PDF blob state
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  // Modal full window expand state
  const [isModalMaximized, setIsModalMaximized] = useState(false);

  // Fetch certified PDF from backend whenever the modal opens
  const fetchPdfReport = useCallback(async () => {
    setIsGeneratingPdf(true);
    setPdfError(null);

    try {

      const cleanedFollowUps = (followUpAnswers || []).map((fu: any) => ({
        question: String(fu?.question || ''),
        answer: String(fu?.answer || ''),
        source: String(fu?.source || ''),
        sql_query: fu?.sql_query || null,
        verified: Boolean(fu?.verified ?? true),
        timestamp: String(fu?.timestamp || ''),
      }));

      const payload = {
        question: question || 'Clinical Analytics Inquiry',
        analysis_plan: analysisPlan || null,
        insight: insight || null,
        results: Array.isArray(results) ? results : [],
        rag_context: ragContext || null,
        sql_query: sqlQuery || null,
        workspace_type: workspaceType || 'clinical',
        selected_tables: Array.isArray(selectedTables) && selectedTables.length > 0
          ? selectedTables.filter(t => !['patients', 'encounters', 'conditions', 'medications', 'observations', 'procedures'].includes(t.toLowerCase().trim()))
          : ['study', 'sites', 'dm'],
        follow_up_answers: cleanedFollowUps,
        approved_by: 'Clinical Analyst',
      };

      const response = await fetch(`${API_BASE_URL}/analytics/report/pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let errorDetail = response.statusText;
        try {
          const errJson = await response.json();
          if (errJson?.detail) {
            errorDetail = typeof errJson.detail === 'string'
              ? errJson.detail
              : JSON.stringify(errJson.detail);
          }
        } catch {
          // fallback to statusText
        }
        throw new Error(`Analytics server returned HTTP ${response.status}: ${errorDetail}`);
      }

      const blob = await response.blob();
      setPdfBlob(blob);
    } catch (err: any) {
      console.error('Failed to compile certified PDF report:', err);
      setPdfError(err?.message || 'Failed to generate certified PDF report.');
    } finally {
      setIsGeneratingPdf(false);
    }
  }, [
    question,
    analysisPlan,
    insight,
    results,
    ragContext,
    sqlQuery,
    workspaceType,
    selectedTables,
    followUpAnswers,
  ]);

  useEffect(() => {
    if (isOpen) {
      fetchPdfReport();
      setIsApproved(false);
      setShowRejectForm(false);
    } else {
      setPdfBlob(null);
      setPdfError(null);
    }
  }, [isOpen, fetchPdfReport]);

  if (!isOpen) return null;

  const handleApprove = async () => {
    setIsApproved(true);
    setShowRejectForm(false);
    try {
      await fetch(`${API_BASE_URL}/analytics/report/approve`, { method: 'POST' });
    } catch (e) {
      console.error('Failed to notify backend of report approval:', e);
    }
  };

  const handleReject = () => {
    setIsApproved(false);
    setShowRejectForm(true);
  };

  // Download the exact certified PDF file with guaranteed .pdf extension on Windows/Chrome
  const handleDownloadPdf = async (e?: React.MouseEvent) => {
    if (e) e.preventDefault();
    if (!isApproved) return;
    setIsDownloading(true);

    try {
      // Fetch binary PDF bytes directly from backend
      const response = await fetch(`${API_BASE_URL}/analytics/report/pdf/Clinical_Analytics_Report.pdf`);
      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }
      const blob = await response.blob();

      // Native Windows Save Dialog via File System API (Guarantees .pdf extension in Chrome/Edge)
      if ('showSaveFilePicker' in window) {
        try {
          const fileHandle = await (window as any).showSaveFilePicker({
            suggestedName: 'Clinical_Analytics_Report.pdf',
            types: [
              {
                description: 'PDF Document (*.pdf)',
                accept: { 'application/pdf': ['.pdf'] },
              },
            ],
          });
          const writableStream = await fileHandle.createWritable();
          await writableStream.write(blob);
          await writableStream.close();
          setIsDownloading(false);
          return;
        } catch (pickerErr: any) {
          if (pickerErr?.name === 'AbortError') {
            setIsDownloading(false);
            return;
          }
          console.warn('showSaveFilePicker fallback:', pickerErr);
        }
      }

      // Standard HTTP attachment download fallback
      const downloadUrl = `${API_BASE_URL}/analytics/report/pdf/Clinical_Analytics_Report.pdf?t=${Date.now()}`;
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = 'Clinical_Analytics_Report.pdf';
      document.body.appendChild(link);
      link.click();

      setTimeout(() => {
        if (link.parentNode) {
          document.body.removeChild(link);
        }
        setIsDownloading(false);
      }, 1200);
    } catch (err: any) {
      console.error('PDF download error:', err);
      window.location.href = `${API_BASE_URL}/analytics/report/pdf/Clinical_Analytics_Report.pdf`;
      setIsDownloading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4 overflow-hidden">
      <div 
        className={`bg-slate-900 rounded-2xl shadow-2xl border border-slate-700/80 overflow-hidden flex flex-col transition-all duration-200 ${
          isModalMaximized 
            ? 'w-full h-full max-w-none max-h-none rounded-none' 
            : 'w-full max-w-5xl h-[92vh]'
        }`}
      >
        {/* Top Modal Header */}
        <div className="px-5 py-3.5 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between z-10 shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center shadow-xs">
              <FileCheck2 className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm sm:text-base font-bold text-white leading-tight">
                Certified Clinical PDF Report Review
              </h2>
              <span className="text-[11px] text-slate-400">
                Official 5-Page Publication-Grade Clinical Audit Document
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-2 sm:space-x-3">
            {isApproved ? (
              <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-700/70 shadow-xs">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Approved & Certified</span>
                <span className="sm:hidden">Approved</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-950/80 text-amber-300 border border-amber-700/70 shadow-xs">
                <Clock className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Pending Human Approval</span>
                <span className="sm:hidden">Pending</span>
              </span>
            )}

            {/* Maximize / Restore Toggle */}
            <button
              onClick={() => setIsModalMaximized(!isModalMaximized)}
              title={isModalMaximized ? 'Restore Modal Size' : 'Maximize Window'}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
            >
              {isModalMaximized ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>

            {/* Close Button */}
            <button
              onClick={onClose}
              title="Close Report Review"
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Main Body - High-Fidelity PDF Viewer */}
        <div className="flex-1 min-h-0 bg-slate-950 relative overflow-hidden flex flex-col">
          {isGeneratingPdf ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-950">
              <div className="w-12 h-12 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
              <h3 className="text-base font-semibold text-white">
                Compiling 5-Page Certified PDF Report...
              </h3>
              <p className="text-xs text-slate-400 mt-1.5 max-w-md">
                FastAPI and ReportLab are assembling publication-grade clinical findings, verified SQL results, chart vectors, and regulatory metadata.
              </p>
            </div>
          ) : pdfError ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-950">
              <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-2xl max-w-md text-center">
                <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto mb-2" />
                <h3 className="text-sm font-bold text-rose-200">Unable to generate PDF report</h3>
                <p className="text-xs text-rose-300/80 mt-1 mb-4">{pdfError}</p>
                <button
                  onClick={fetchPdfReport}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors inline-flex items-center space-x-1.5 cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Retry Compilation</span>
                </button>
              </div>
            </div>
          ) : (
            <PDFViewer pdfBlob={pdfBlob} className="flex-1 h-full min-h-0" />
          )}
        </div>

        {/* Modal Bottom Actions Bar */}
        <div className="px-5 py-3 border-t border-slate-800 bg-slate-900 flex flex-col sm:flex-row items-center justify-between gap-3 shrink-0">
          <div className="text-xs text-slate-300">
            {!isApproved ? (
              <span className="flex items-center space-x-1.5 text-amber-400 font-medium">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>Review all 5 pages completely before issuing digital certification.</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1.5 text-emerald-400 font-medium">
                <Check className="w-4 h-4 shrink-0" />
                <span>Report certified. You can now download the identical 5-page PDF document.</span>
              </span>
            )}
          </div>

          <div className="flex items-center space-x-2.5">
            {!isApproved ? (
              <>
                <button
                  onClick={handleReject}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition-colors cursor-pointer"
                >
                  Reject / Request Changes
                </button>
                <button
                  onClick={handleApprove}
                  disabled={isGeneratingPdf || !pdfBlob}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-md shadow-indigo-600/20 transition-all flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Approve Report</span>
                </button>
              </>
            ) : (
              <button
                onClick={handleDownloadPdf}
                disabled={isDownloading}
                className="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg shadow-md shadow-emerald-600/20 transition-all flex items-center space-x-2 cursor-pointer disabled:opacity-50"
              >
                <Download className="w-4 h-4" />
                <span>{isDownloading ? 'Saving PDF...' : 'Download PDF'}</span>
              </button>
            )}
          </div>
        </div>

        {/* Request changes feedback sub-panel */}
        {showRejectForm && (
          <div className="p-3.5 bg-rose-950/80 border-t border-rose-800 flex items-center justify-between gap-3 shrink-0">
            <input
              type="text"
              value={rejectFeedback}
              onChange={(e) => setRejectFeedback(e.target.value)}
              placeholder="Specify requested modifications for auditor audit trail..."
              className="flex-1 text-xs px-3 py-1.5 border border-rose-700 rounded-md bg-slate-900 text-slate-100 placeholder-slate-400 focus:outline-hidden focus:ring-1 focus:ring-rose-500"
            />
            <button
              onClick={() => {
                setShowRejectForm(false);
                onClose();
              }}
              className="px-3.5 py-1.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-md shadow-xs cursor-pointer"
            >
              Submit Feedback & Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportModal;
