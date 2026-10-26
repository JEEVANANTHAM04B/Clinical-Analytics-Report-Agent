import React, { useMemo, useState } from 'react';
import { UserCheck, Check, AlertCircle, RefreshCw, GitCommit } from 'lucide-react';
import { summarizeClinicalPlan } from './clinicalPlanSummary';

interface ClinicalApprovalCardProps {
  analysisPlan: string;
  question?: string;
  audience?: 'clinical' | 'technical';
  onApprove: () => void;
  onReject: (feedback: string) => void;
  isLoading?: boolean;
  isRegenerating?: boolean;
  planVersion?: number;
  feedbackHistory?: string[];
  elapsedSecs?: number;
  errorMessage?: string | null;
}

export const ClinicalApprovalCard: React.FC<ClinicalApprovalCardProps> = ({
  analysisPlan,
  question = '',
  audience = 'clinical',
  onApprove,
  onReject,
  isLoading = false,
  isRegenerating = false,
  planVersion = 1,
  feedbackHistory = [],
  elapsedSecs = 0,
  errorMessage,
}) => {
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [feedback, setFeedback] = useState('');

  const handleRejectSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onReject(feedback);
    setShowFeedbackModal(false);
    setFeedback('');
  };

  const isRevised = planVersion > 1;
  const summary = useMemo(() => summarizeClinicalPlan(analysisPlan, question), [analysisPlan, question]);

  return (
    <section aria-label="Review analysis plan" className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
      {/* Header */}
      <div className="mb-5 flex flex-col justify-between gap-3 border-b border-slate-200 pb-4 sm:flex-row sm:items-center">
        <div className="flex items-center space-x-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-white">
            <UserCheck className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm sm:text-base font-bold text-gray-900 leading-tight tracking-tight">
                REVIEW ANALYSIS PLAN
              </h3>
              {isRevised && (
                <span className="px-2 py-0.5 text-[10px] font-bold bg-indigo-100 text-indigo-700 rounded-full border border-indigo-200 flex items-center space-x-1">
                  <GitCommit className="w-3 h-3" />
                  <span>v{planVersion} Revised</span>
                </span>
              )}
            </div>
            <p className="text-[11px] text-gray-600 mt-0.5">
              {isRevised
                ? 'Review the updated clinical approach before continuing.'
                : 'Confirm that this clinical approach matches your question before continuing.'}
            </p>
          </div>
        </div>

        <span className="self-start rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700 sm:self-auto">
          {isRevised ? 'Revised plan' : 'Awaiting review'}
        </span>
      </div>

      {feedbackHistory && feedbackHistory.length > 0 && (
        <p className="mb-4 text-xs text-slate-600">Updated using your {feedbackHistory.length} previous revision {feedbackHistory.length === 1 ? 'request' : 'requests'}.</p>
      )}

      {/* Regenerating Spinner Indicator */}
      {isRegenerating ? (
        <div className="mb-4 rounded-lg border border-indigo-200 bg-indigo-50 p-6 text-center">
          <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin mb-2" />
          <h4 className="text-xs font-bold text-gray-900">
            Updating the analysis plan...
          </h4>
          <p className="text-[11px] text-gray-500 mt-0.5 max-w-md">
            Applying your feedback to the proposed clinical approach.
          </p>
        </div>
      ) : (
        audience === 'technical' ? (
          <pre className="mb-5 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-800">{analysisPlan}</pre>
        ) : (
        <div className="mb-5 grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 md:col-span-2">
            <h4 className="mb-1 text-sm font-semibold text-slate-900">Analysis Objective</h4>
            <p className="text-sm leading-relaxed text-slate-700">{summary.objective}</p>
          </div>
          {([
            ['What I will analyze', summary.analyze],
            ['How I will perform the analysis', summary.method],
            ['Expected Output', summary.output],
          ] as const).map(([title, items]) => (
            <div key={title} className="rounded-lg border border-slate-200 bg-white p-4">
              <h4 className="mb-2 text-sm font-semibold text-slate-900">{title}</h4>
              <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-slate-700">
                {items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          ))}
          {summary.limitation && (
            <p role="note" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 md:col-span-2">
              {summary.limitation}
            </p>
          )}
        </div>
        )
      )}

      {/* Actions */}
      {errorMessage && (
        <p role="alert" className="mb-3 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-xs text-rose-800">
          {errorMessage}
        </p>
      )}
      <div className="flex flex-col gap-3 border-t border-slate-200 pt-4 sm:flex-row sm:items-center sm:justify-end">
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={() => setShowFeedbackModal(true)}
            disabled={isLoading || isRegenerating}
            className="flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50"
          >
            Revise Plan
          </button>

          <button
            type="button"
            onClick={onApprove}
            disabled={isLoading || isRegenerating}
            className="flex items-center space-x-1.5 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Processing analysis{elapsedSecs > 0 ? ` (${elapsedSecs}s)` : '...'}</span>
              </>
            ) : (
              <>
                <Check className="w-3.5 h-3.5" />
                <span>Approve &amp; Continue</span>
              </>
            )}
          </button>
        </div>
      </div>
      {/* Pipeline progress hint shown while loading */}
      {isLoading && (
        <div className="mt-2 px-3 py-2 bg-indigo-50 border border-indigo-200 rounded-lg text-[11px] text-indigo-700 flex items-center gap-2">
          <RefreshCw className="w-3 h-3 animate-spin flex-shrink-0" />
          <span>
            Preparing and validating your clinical analysis
            {elapsedSecs > 0 && (
              <> &mdash; <span className="font-bold">{elapsedSecs}s elapsed</span>. This typically takes 60&ndash;120 seconds.</>
            )}
          </span>
        </div>
      )}

      {/* Rejection Modal */}
      {showFeedbackModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-2xl border border-gray-200 animate-scaleIn">
            <div className="flex items-center space-x-2 text-rose-600 mb-2">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <h4 className="text-base font-bold text-gray-900">
                {isRevised ? 'Revise the Plan Again' : 'Revise Analysis Plan'}
              </h4>
            </div>
            <p className="text-xs text-gray-600 mb-4 leading-relaxed">
              Describe what should change in the clinical approach. You will review the updated plan before analysis continues.
            </p>

            <form onSubmit={handleRejectSubmit}>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Revision Request (Optional):
              </label>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="e.g. Please group the analysis by diagnosis and only include inpatient encounters."
                rows={4}
                className="w-full text-xs p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-hidden mb-4 text-gray-900 placeholder-gray-400 bg-white"
                autoFocus
              />

              <div className="flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowFeedbackModal(false)}
                  className="px-3.5 py-1.5 text-xs text-gray-600 hover:bg-gray-100 rounded-lg transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors cursor-pointer"
                >
                  Request Revised Plan
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
};

export default ClinicalApprovalCard;
