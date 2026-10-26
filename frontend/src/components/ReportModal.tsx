import React, { useEffect, useState, useCallback, useRef } from 'react';
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

const EMPTY_RESULTS: Record<string, any>[] = [];
const EMPTY_FOLLOW_UPS: { question: string; answer: string }[] = [];

interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  question: string;
  analysisPlan?: string | null;
  insight?: string | null;
  results?: Record<string, any>[];
  sqlQuery?: string | null;
  workspaceType?: 'clinical' | 'technical';
  selectedTables?: string[];
  followUpAnswers?: { question: string; answer: string }[];
  datasetName?: string | null;
  analysisRunId?: string | null;
  onAcknowledged?: () => void;
}

export const ReportModal: React.FC<ReportModalProps> = ({
  isOpen,
  onClose,
  question,
  analysisPlan,
  insight,
  results = EMPTY_RESULTS,
  sqlQuery,
  workspaceType = 'clinical',
  selectedTables,
  followUpAnswers = EMPTY_FOLLOW_UPS,
  datasetName,
  analysisRunId,
  onAcknowledged,
}) => {
  const [isApproved, setIsApproved] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [rejectFeedback, setRejectFeedback] = useState('');
  const [showRejectForm, setShowRejectForm] = useState(false);

  // PDF blob state
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [reportId, setReportId] = useState<string | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [studyId, setStudyId] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const savingRef = useRef(false);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const needsAnalysis = !analysisRunId && results.length === 0;

  // Modal full window expand state
  const [isModalMaximized, setIsModalMaximized] = useState(false);

  // Generate the PDF for the current session whenever the modal opens.
  const fetchPdfReport = useCallback(async () => {
    setIsGeneratingPdf(true);
    setPdfError(null);
    setPdfBlob(null);
    setReportId(null);
    setGeneratedAt(null);
    setStudyId(null);
    setIsApproved(false);

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
        sql_query: sqlQuery || null,
        workspace_type: workspaceType || 'clinical',
        selected_tables: Array.isArray(selectedTables) && selectedTables.length > 0
          ? selectedTables : [],
        analysis_run_id: analysisRunId || null,
        dataset_name: datasetName || null,
        follow_up_answers: cleanedFollowUps,
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
        if (response.status === 403 && /not authenticated/i.test(errorDetail)) {
          throw new Error('The running analytics server still requires authentication. Restart the updated backend on port 8001, then retry PDF generation.');
        }
        throw new Error(`Analytics server returned HTTP ${response.status}: ${errorDetail}`);
      }

      const blob = await response.blob();
      const id = response.headers.get('X-Report-ID');
      if (!id) throw new Error('The analytics server did not provide a report ID. Restart the updated backend and retry.');
      setPdfBlob(blob);
      setReportId(id);
      setGeneratedAt(response.headers.get('X-Report-Generated-At'));
      setStudyId(response.headers.get('X-Report-Study-ID'));
    } catch (err: any) {
      console.error('Failed to generate PDF report:', err);
      setPdfError(err?.message || 'Failed to generate PDF report.');
    } finally {
      setIsGeneratingPdf(false);
    }
  }, [
    question,
    analysisRunId,
    analysisPlan,
    insight,
    results,
    sqlQuery,
    workspaceType,
    selectedTables,
    followUpAnswers,
    datasetName,
  ]);

  useEffect(() => {
    if (isOpen) {
      setIsApproved(false);
      setShowRejectForm(false);
      if (needsAnalysis) {
        setPdfBlob(null);
        setPdfError(null);
        return;
      }
      const timer = window.setTimeout(() => { void fetchPdfReport(); }, 250);
      return () => window.clearTimeout(timer);
    } else {
      setPdfBlob(null);
      setReportId(null);
      setPdfError(null);
      setDownloadError(null);
    }
  }, [isOpen, needsAnalysis, fetchPdfReport]);

  if (!isOpen) return null;

  const handleApprove = async () => {
    if (!pdfBlob || !reportId || savingRef.current || isApproved) return;
    savingRef.current = true;
    setIsSaving(true);
    setDownloadError(null);
    try {
      const form = new FormData();
      form.append('report_id', reportId);
      form.append('question', question || 'Clinical Analytics Inquiry');
      form.append('pdf', pdfBlob, `clinical-report-${reportId}.pdf`);
      if (datasetName) form.append('dataset_name', datasetName);
      if (analysisRunId) form.append('analysis_run_id', analysisRunId);
      if (studyId) form.append('study_id', studyId);
      if (generatedAt) form.append('generated_at', generatedAt);
      const response = await fetch(`${API_BASE_URL}/reports/acknowledge`, { method: 'POST', body: form });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(typeof detail?.detail === 'string' ? detail.detail : `Could not save report (HTTP ${response.status}).`);
      }
      setIsApproved(true);
      setShowRejectForm(false);
      onAcknowledged?.();
    } catch (err: any) {
      setDownloadError(err?.message || 'Could not save the acknowledged report. Please retry.');
    } finally {
      savingRef.current = false;
      setIsSaving(false);
    }
  };

  const handleReject = () => {
    setIsApproved(false);
    setShowRejectForm(true);
  };

  const handleDownloadPdf = async (e?: React.MouseEvent) => {
    if (e) e.preventDefault();
    if (!isApproved || !pdfBlob) return;
    setIsDownloading(true);
    setDownloadError(null);

    try {
      const blob = pdfBlob;
      const filename = `clinical-report-${new Date().toISOString().slice(0, 10)}.pdf`;

      if ('showSaveFilePicker' in window) {
        try {
          const fileHandle = await (window as any).showSaveFilePicker({
            suggestedName: filename,
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
          if (pickerErr?.name !== 'AbortError') console.warn('showSaveFilePicker fallback:', pickerErr);
        }
      }

      const downloadUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
    } catch (err: any) {
      console.error('PDF download error:', err);
      setDownloadError(err?.message || 'The generated PDF could not be downloaded.');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-[#111827]/35 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4 overflow-hidden">
      <div 
        className={`bg-[#ffffff] rounded-2xl shadow-2xl border border-[#E5E7EB] overflow-hidden flex flex-col transition-all duration-200 ${
          isModalMaximized 
            ? 'w-full h-full max-w-none max-h-none rounded-none' 
            : 'w-full max-w-5xl h-[92vh]'
        }`}
      >
        {/* Top Modal Header */}
        <div className="px-5 py-4 border-b border-[#E5E7EB] bg-[#ffffff] flex items-center justify-between z-10 shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-[#EEF2FF] text-[#4F46E5] flex items-center justify-center">
              <FileCheck2 className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-semibold text-[#111827] leading-tight">
                Clinical PDF Report Review
              </h2>
              <span className="text-xs text-[#64748B]">
                A4 report following the clinical safety template
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-2 sm:space-x-3">
            {needsAnalysis ? (
              <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE]">
                Analysis required
              </span>
            ) : isApproved ? (
              <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Review acknowledged</span>
                <span className="sm:hidden">Reviewed</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                <Clock className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Pending Human Approval</span>
                <span className="sm:hidden">Pending</span>
              </span>
            )}

            {/* Maximize / Restore Toggle */}
            <button
              onClick={() => setIsModalMaximized(!isModalMaximized)}
              title={isModalMaximized ? 'Restore Modal Size' : 'Maximize Window'}
              className="p-1.5 rounded-lg text-[#64748B] hover:text-[#111827] hover:bg-[#EEF2FF] transition-colors cursor-pointer"
            >
              {isModalMaximized ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>

            {/* Close Button */}
            <button
              onClick={onClose}
              title="Close Report Review"
              className="p-1.5 rounded-lg text-[#64748B] hover:text-[#111827] hover:bg-[#EEF2FF] transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Main Body - High-Fidelity PDF Viewer */}
        <div className="flex-1 min-h-0 bg-[#F8FAFC] relative overflow-hidden flex flex-col">
          {needsAnalysis ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[#F8FAFC]">
              <div className="max-w-md rounded-2xl border border-[#E5E7EB] bg-[#ffffff] p-7 shadow-sm">
                <FileCheck2 className="w-9 h-9 text-[#4F46E5] mx-auto mb-3" />
                <h3 className="text-lg font-semibold text-[#111827]">Complete an analysis to create a PDF</h3>
                <p className="text-sm text-[#64748B] mt-2 leading-relaxed">
                  Run a clinical question through result validation, then return here to review and export its report.
                </p>
                <button onClick={onClose} className="mt-5 px-5 py-2.5 bg-[#4F46E5] hover:bg-[#4338CA] text-white text-sm font-semibold rounded-lg cursor-pointer">
                  Return to workspace
                </button>
              </div>
            </div>
          ) : isGeneratingPdf ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[#F8FAFC]">
              <div className="w-12 h-12 border-3 border-[#4F46E5] border-t-transparent rounded-full animate-spin mb-4" />
              <h3 className="text-base font-semibold text-[#111827]">
                Preparing Clinical PDF Report...
              </h3>
              <p className="text-sm text-[#64748B] mt-1.5 max-w-md">
                Assembling the supplied analysis, result table, chart, interpretation, and traceability record.
              </p>
            </div>
          ) : pdfError ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[#F8FAFC]">
              <div className="p-5 bg-rose-50 border border-rose-200 rounded-2xl max-w-md text-center">
                <AlertTriangle className="w-8 h-8 text-rose-600 mx-auto mb-2" />
                <h3 className="text-sm font-bold text-rose-800">Unable to generate PDF report</h3>
                <p className="text-xs text-rose-700 mt-1 mb-4">{pdfError}</p>
                <button
                  onClick={fetchPdfReport}
                  className="px-4 py-2 bg-[#4F46E5] hover:bg-[#4338CA] text-white text-xs font-semibold rounded-lg shadow-sm transition-colors inline-flex items-center space-x-1.5 cursor-pointer"
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
        <div className="px-5 py-4 border-t border-[#E5E7EB] bg-[#ffffff] flex flex-col sm:flex-row items-center justify-between gap-3 shrink-0">
          <div className="text-xs text-[#64748B]">
            {needsAnalysis ? (
              <span>Report generation becomes available after an analysis produces validated results.</span>
            ) : !isApproved ? (
              <span className="flex items-center space-x-1.5 text-amber-800 font-medium">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>Review the report and its data-quality limitations before acknowledging it.</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1.5 text-emerald-800 font-medium">
                <Check className="w-4 h-4 shrink-0" />
                <span>Review acknowledged and saved to Report History. You can download the PDF.</span>
              </span>
            )}
          </div>
          {downloadError && <p role="alert" className="text-xs text-rose-700">{downloadError}</p>}

          {!needsAnalysis && <div className="flex items-center space-x-2.5">
            {!isApproved ? (
              <>
                <button
                  onClick={handleReject}
                  className="px-4 py-2 bg-white hover:bg-[#EEF2FF] border border-[#CBD5E1] text-[#111827] text-xs font-semibold rounded-lg transition-colors cursor-pointer"
                >
                  Reject / Request Changes
                </button>
                <button
                  onClick={handleApprove}
                  disabled={isGeneratingPdf || isSaving || !pdfBlob || !reportId}
                  className="px-5 py-2 bg-[#4F46E5] hover:bg-[#4338CA] text-white text-xs font-semibold rounded-lg shadow-sm transition-all flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>{isSaving ? 'Saving report...' : 'Acknowledge Review'}</span>
                </button>
              </>
            ) : (
              <button
                onClick={handleDownloadPdf}
                disabled={isDownloading}
                className="px-6 py-2 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold rounded-lg shadow-sm transition-all flex items-center space-x-2 cursor-pointer disabled:opacity-50"
              >
                <Download className="w-4 h-4" />
                <span>{isDownloading ? 'Saving PDF...' : 'Download PDF'}</span>
              </button>
            )}
          </div>}
        </div>

        {/* Request changes feedback sub-panel */}
        {showRejectForm && (
          <div className="p-3.5 bg-rose-50 border-t border-rose-200 flex items-center justify-between gap-3 shrink-0">
            <input
              type="text"
              value={rejectFeedback}
              onChange={(e) => setRejectFeedback(e.target.value)}
              placeholder="Specify requested modifications..."
              className="flex-1 text-xs px-3 py-1.5 border border-rose-200 rounded-md bg-white text-[#111827] placeholder-[#94A3B8] focus:outline-hidden focus:ring-1 focus:ring-rose-500"
            />
            <button
              onClick={() => {
                setShowRejectForm(false);
                onClose();
              }}
              className="px-3.5 py-1.5 bg-rose-700 hover:bg-rose-800 text-white text-xs font-semibold rounded-md shadow-xs cursor-pointer"
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
