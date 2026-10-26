import React, { useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  SkipForward,
  X,
  Database,
  FileSpreadsheet,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react';
import { UploadDatasetResponse } from '../api/datasets';

type IngestionState = 'success' | 'already_exists' | 'partial' | 'failed';

interface IngestionResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  response: UploadDatasetResponse | null;
  errorMessage?: string | null;
}

function useCopyToClipboard() {
  const [copied, setCopied] = useState(false);
  const copy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return { copied, copy };
}

function resolveIngestionState(
  response: UploadDatasetResponse | null,
  errorMessage?: string | null,
): IngestionState {
  if (errorMessage || !response || response.status !== 'success') return 'failed';
  const inserted = response.rows_inserted ?? response.rows_loaded ?? 0;
  const skipped  = response.rows_skipped  ?? 0;
  const failed   = response.rows_failed   ?? 0;
  if (failed > 0)                    return 'failed';
  if (inserted === 0 && skipped > 0) return 'already_exists';
  if (inserted > 0  && skipped > 0)  return 'partial';
  return 'success';
}

interface StatRowProps {
  label: string;
  value: string | number;
  valueColor?: string;
}
const StatRow: React.FC<StatRowProps> = ({ label, value, valueColor = 'text-gray-900' }) => (
  <div className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
    <span className="text-[11px] text-gray-500">{label}</span>
    <span className={`text-[11px] font-bold ${valueColor} font-mono`}>{value}</span>
  </div>
);

export const IngestionResultModal: React.FC<IngestionResultModalProps> = ({
  isOpen,
  onClose,
  response,
  errorMessage,
}) => {
  const [showRaw, setShowRaw] = useState(false);
  const { copied, copy } = useCopyToClipboard();

  if (!isOpen) return null;

  const ingestionState = resolveIngestionState(response, errorMessage);

  const sourceFilename =
    response?.dataset?.original_filename ||
    response?.dataset?.saved_filename    ||
    response?.dataset?.file_name         ||
    '';

  const targetTable  = response?.table_name  ?? '—';
  const rowsReceived = response?.rows_received  ?? response?.dataset?.row_count ?? 0;
  const rowsInserted = response?.rows_inserted  ?? response?.rows_loaded        ?? 0;
  const rowsSkipped  = response?.rows_skipped   ?? 0;
  const rowsFailed   = response?.rows_failed    ?? 0;
  const columnCount  = response?.columns        ?? response?.dataset?.column_count ?? 0;

  // --- Per-state config ---
  type StateCfg = {
    title: string; subtitle: string; statusLabel: string;
    headerBg: string; headerBorder: string; border: string;
    titleColor: string; subColor: string; badgeBg: string;
    badgeText: string; badgeBorder: string; btnBg: string;
    dbStatus: string; dbBg: string; dbBorder: string;
    infoBg: string; infoBorder: string; infoText: string;
    headerIcon: React.ReactNode; badgeIcon: React.ReactNode;
  };

  const CFG: Record<IngestionState, StateCfg> = {
    success: {
      title: 'Dataset Ingestion Successful',
      subtitle: 'New data successfully loaded into MySQL',
      statusLabel: 'Success',
      headerBg: 'bg-emerald-50', headerBorder: 'border-emerald-100', border: 'border-emerald-200',
      titleColor: 'text-emerald-900', subColor: 'text-emerald-600',
      badgeBg: 'bg-emerald-100', badgeText: 'text-emerald-700', badgeBorder: 'border-emerald-200',
      btnBg: 'bg-emerald-600 hover:bg-emerald-500',
      dbStatus: 'New rows added to database', dbBg: 'bg-emerald-50', dbBorder: 'border-emerald-200',
      infoBg: 'bg-emerald-50', infoBorder: 'border-emerald-200', infoText: 'text-emerald-700',
      headerIcon: <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />,
      badgeIcon:  <Check className="w-2.5 h-2.5" />,
    },
    already_exists: {
      title: 'Dataset Already Exists',
      subtitle: 'No new rows were added to the database',
      statusLabel: 'Processed',
      headerBg: 'bg-amber-50', headerBorder: 'border-amber-100', border: 'border-amber-300',
      titleColor: 'text-amber-900', subColor: 'text-amber-600',
      badgeBg: 'bg-amber-100', badgeText: 'text-amber-700', badgeBorder: 'border-amber-200',
      btnBg: 'bg-amber-500 hover:bg-amber-400',
      dbStatus: 'No changes made', dbBg: 'bg-amber-50', dbBorder: 'border-amber-200',
      infoBg: 'bg-amber-50', infoBorder: 'border-amber-200', infoText: 'text-amber-800',
      headerIcon: <SkipForward className="w-4 h-4 text-amber-600 flex-shrink-0" />,
      badgeIcon:  <Check className="w-2.5 h-2.5" />,
    },
    partial: {
      title: 'Dataset Partially Loaded',
      subtitle: 'Some new records added; existing records skipped',
      statusLabel: 'Partial',
      headerBg: 'bg-sky-50', headerBorder: 'border-sky-100', border: 'border-sky-200',
      titleColor: 'text-sky-900', subColor: 'text-sky-600',
      badgeBg: 'bg-sky-100', badgeText: 'text-sky-700', badgeBorder: 'border-sky-200',
      btnBg: 'bg-sky-600 hover:bg-sky-500',
      dbStatus: 'Partial update applied', dbBg: 'bg-sky-50', dbBorder: 'border-sky-200',
      infoBg: 'bg-sky-50', infoBorder: 'border-sky-200', infoText: 'text-sky-800',
      headerIcon: <AlertTriangle className="w-4 h-4 text-sky-600 flex-shrink-0" />,
      badgeIcon:  <Check className="w-2.5 h-2.5" />,
    },
    failed: {
      title: 'Ingestion Failed',
      subtitle: 'Backend returned an error',
      statusLabel: 'Failed',
      headerBg: 'bg-rose-50', headerBorder: 'border-rose-100', border: 'border-rose-200',
      titleColor: 'text-rose-900', subColor: 'text-rose-600',
      badgeBg: 'bg-rose-100', badgeText: 'text-rose-700', badgeBorder: 'border-rose-200',
      btnBg: 'bg-rose-600 hover:bg-rose-500',
      dbStatus: 'No changes made', dbBg: 'bg-rose-50', dbBorder: 'border-rose-200',
      infoBg: 'bg-rose-50', infoBorder: 'border-rose-100', infoText: 'text-rose-700',
      headerIcon: <XCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />,
      badgeIcon:  <X className="w-2.5 h-2.5" />,
    },
  };

  const cfg = CFG[ingestionState];

  function buildExplanation(): string {
    switch (ingestionState) {
      case 'success':
        return `${rowsInserted.toLocaleString()} new record${rowsInserted === 1 ? '' : 's'} were successfully inserted into the "${targetTable}" table.`;
      case 'already_exists':
        return `All ${rowsReceived.toLocaleString()} uploaded records already exist in the "${targetTable}" table, so they were skipped to prevent duplicate records. The database was not changed.`;
      case 'partial':
        return `${rowsInserted.toLocaleString()} new record${rowsInserted === 1 ? '' : 's'} were inserted into "${targetTable}". ${rowsSkipped.toLocaleString()} existing record${rowsSkipped === 1 ? '' : 's'} were skipped to prevent duplicates.`;
      case 'failed':
        return response?.message ?? errorMessage ?? 'An unexpected error occurred during ingestion.';
    }
  }

  const rawJson = response
    ? JSON.stringify({
        status:        response.status,
        message:       response.message,
        table_name:    response.table_name,
        rows_loaded:   response.rows_loaded,
        rows_received: response.rows_received,
        rows_inserted: response.rows_inserted,
        rows_skipped:  response.rows_skipped,
        rows_failed:   response.rows_failed,
        columns:       response.columns,
        dataset: response.dataset ? {
          original_filename: response.dataset.original_filename,
          file_type:         response.dataset.file_type,
          row_count:         response.dataset.row_count,
          column_count:      response.dataset.column_count,
        } : undefined,
      }, null, 2)
    : (errorMessage ?? '');

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-end p-6 pointer-events-none"
      aria-modal="true"
      role="dialog"
    >
      <div
        className={`pointer-events-auto w-full max-w-sm bg-white rounded-2xl shadow-2xl border ${cfg.border} flex flex-col overflow-hidden`}
        style={{ animation: 'ingestionSlideUp 0.28s cubic-bezier(0.16,1,0.3,1) both' }}
      >
        {/* Header */}
        <div className={`px-4 py-3 flex items-center justify-between ${cfg.headerBg} border-b ${cfg.headerBorder}`}>
          <div className="flex items-center gap-2">
            {cfg.headerIcon}
            <div>
              <p className={`text-xs font-bold leading-tight ${cfg.titleColor}`}>{cfg.title}</p>
              <p className={`text-[10px] leading-tight mt-0.5 ${cfg.subColor}`}>{cfg.subtitle}</p>
            </div>
          </div>
          <button onClick={onClose} className={`p-1 rounded-lg transition-colors ${cfg.subColor} hover:opacity-80`} aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-3">

          {/* Status badge */}
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Status</span>
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${cfg.badgeBg} ${cfg.badgeText} ${cfg.badgeBorder}`}>
              {cfg.badgeIcon}
              {cfg.statusLabel}
            </span>
          </div>

          {/* Dataset & table chips */}
          {(sourceFilename || targetTable !== '—') && (
            <div className="space-y-1">
              {sourceFilename && (
                <div className="flex items-center gap-1.5 bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2">
                  <FileSpreadsheet className="w-3 h-3 text-indigo-500 flex-shrink-0" />
                  <span className="text-[10px] text-indigo-600 font-semibold truncate" title={sourceFilename}>{sourceFilename}</span>
                </div>
              )}
              {targetTable !== '—' && (
                <div className="flex items-center gap-1.5 bg-sky-50 border border-sky-100 rounded-lg px-3 py-2">
                  <Database className="w-3 h-3 text-sky-500 flex-shrink-0" />
                  <span className="text-[10px] text-sky-600 font-semibold">
                    Target Table: <span className="font-mono font-bold">{targetTable}</span>
                  </span>
                  {columnCount > 0 && (
                    <span className="ml-auto text-[9px] text-sky-400 font-mono">{columnCount} cols</span>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Row metrics */}
          <div className="bg-gray-50 rounded-xl border border-gray-100 px-3 py-2 space-y-0.5">
            <StatRow label="Rows Received" value={rowsReceived.toLocaleString()} valueColor="text-gray-700" />
            {ingestionState === 'already_exists' ? (
              <>
                <StatRow label="New Rows Inserted" value="0" valueColor="text-gray-400" />
                <StatRow label="Already Existing / Skipped" value={rowsSkipped.toLocaleString()} valueColor="text-amber-600" />
              </>
            ) : ingestionState === 'partial' ? (
              <>
                <StatRow label="New Rows Inserted" value={rowsInserted.toLocaleString()} valueColor="text-emerald-600" />
                <StatRow label="Already Existing / Skipped" value={rowsSkipped.toLocaleString()} valueColor="text-amber-600" />
              </>
            ) : (
              <>
                <StatRow label="Rows Inserted" value={rowsInserted.toLocaleString()} valueColor={rowsInserted > 0 ? 'text-emerald-600' : 'text-gray-400'} />
                <StatRow label="Rows Skipped"  value={rowsSkipped.toLocaleString()}  valueColor={rowsSkipped  > 0 ? 'text-amber-600'  : 'text-gray-400'} />
              </>
            )}
            <StatRow label="Rows Failed" value={rowsFailed.toLocaleString()} valueColor={rowsFailed > 0 ? 'text-rose-600' : 'text-gray-400'} />
          </div>

          {/* DB status */}
          <div className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border ${cfg.dbBg} ${cfg.dbBorder}`}>
            <Database className={`w-3 h-3 flex-shrink-0 ${cfg.subColor}`} />
            <span className={`text-[10px] font-semibold ${cfg.subColor}`}>Database Status:&nbsp;</span>
            <span className={`text-[10px] font-bold ${cfg.titleColor}`}>{cfg.dbStatus}</span>
          </div>

          {/* Explanation */}
          <div className={`flex gap-2 px-3 py-2.5 rounded-xl border ${cfg.infoBg} ${cfg.infoBorder}`}>
            <Info className={`w-3.5 h-3.5 flex-shrink-0 mt-0.5 ${cfg.infoText} opacity-70`} />
            <p className={`text-[11px] leading-relaxed ${cfg.infoText}`}>{buildExplanation()}</p>
          </div>

          {/* View Response JSON */}
          <div>
            <button
              onClick={() => setShowRaw(v => !v)}
              className="flex items-center gap-1.5 text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 transition-colors"
            >
              {showRaw ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              {showRaw ? 'Hide' : 'View'} Response JSON
            </button>
            {showRaw && (
              <div className="mt-2 relative">
                <pre className="text-[10px] font-mono bg-[#F1F5F9] text-[#111827] rounded-xl p-3 overflow-auto max-h-52 leading-relaxed whitespace-pre-wrap break-all border border-[#E5E7EB]">
                  {rawJson}
                </pre>
                <button
                  onClick={() => copy(rawJson)}
                  className="absolute top-2 right-2 flex items-center gap-1 bg-gray-700 hover:bg-gray-600 text-gray-200 text-[9px] font-semibold px-2 py-1 rounded-md transition-colors"
                  title="Copy JSON"
                >
                  {copied ? <Check className="w-2.5 h-2.5 text-emerald-400" /> : <Copy className="w-2.5 h-2.5" />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-4 pb-4 pt-1 flex justify-end">
          <button
            onClick={onClose}
            className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all shadow-sm text-white ${cfg.btnBg}`}
          >
            Close
          </button>
        </div>
      </div>

      <style>{`
        @keyframes ingestionSlideUp {
          from { opacity: 0; transform: translateY(20px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
    </div>
  );
};

export default IngestionResultModal;
