import React, { useCallback, useEffect, useState } from 'react';
import { Download, Eye, FileText, RefreshCw } from 'lucide-react';
import { API_BASE_URL } from '../api/client';

interface ReportHistoryProps {
  onGenerate: () => void;
  refreshKey?: number;
}

interface SavedReport {
  id: string;
  title: string;
  question: string;
  dataset_name: string | null;
  study: { studyid?: string } | null;
  generated_at: string;
  acknowledged_at: string | null;
  status: string;
}

export const ReportHistory: React.FC<ReportHistoryProps> = ({ onGenerate, refreshKey = 0 }) => {
  const [reports, setReports] = useState<SavedReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  const load = useCallback(async (active: () => boolean) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/reports`);
      if (!response.ok) throw new Error(`Report history is unavailable (HTTP ${response.status}).`);
      const items: SavedReport[] = await response.json();
      if (active()) setReports(items);
    } catch (err: any) {
      if (active()) setError(err?.message || 'Report history is unavailable.');
    } finally {
      if (active()) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void load(() => active);
    return () => { active = false; };
  }, [load, refreshKey, retry]);

  return (
    <section className="space-y-5" aria-label="Report history">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Report History</h2>
          <p className="mt-1 text-sm text-gray-500">PDF reports saved after human acknowledgement.</p>
        </div>
        <button onClick={onGenerate} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
          Generate report
        </button>
      </header>
      {loading ? (
        <div className="rounded-xl border border-gray-200 bg-white p-10 text-center text-gray-500">Loading saved reports...</div>
      ) : error ? (
        <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-rose-800">
          {error}
          <button onClick={() => setRetry((value) => value + 1)} className="ml-3 inline-flex items-center gap-1 text-sm font-semibold underline"><RefreshCw className="h-4 w-4" />Retry</button>
        </div>
      ) : reports.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center">
          <FileText className="mx-auto h-8 w-8 text-gray-400" />
          <p className="mt-3 font-semibold text-gray-800">No acknowledged reports yet</p>
          <p className="mt-1 text-sm text-gray-500">Generate a report, review its PDF, and acknowledge it to save it here.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((report) => {
            const pdfUrl = `${API_BASE_URL}/reports/${encodeURIComponent(report.id)}/pdf`;
            return (
              <article key={report.id} className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <h3 className="font-semibold text-gray-900">{report.title}</h3>
                    <p className="mt-1 text-sm text-gray-600">{report.question}</p>
                    <p className="mt-2 text-xs text-gray-500">
                      {report.dataset_name ? `${report.dataset_name} · ` : ''}
                      {report.study?.studyid ? `Study ${report.study.studyid} · ` : ''}
                      Generated {new Date(report.generated_at).toLocaleString()} · Acknowledged {report.acknowledged_at ? new Date(report.acknowledged_at).toLocaleString() : '—'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800">{report.status}</span>
                    <a href={pdfUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-2 text-xs font-semibold text-gray-800 hover:bg-gray-50"><Eye className="h-4 w-4" />View</a>
                    <a href={`${pdfUrl}?download=true`} className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-2 text-xs font-semibold text-gray-800 hover:bg-gray-50"><Download className="h-4 w-4" />Download</a>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
};

export default ReportHistory;
