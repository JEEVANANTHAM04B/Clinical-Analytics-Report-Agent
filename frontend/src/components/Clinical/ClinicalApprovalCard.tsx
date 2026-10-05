import React, { useState } from 'react';
import { UserCheck, Check, X, AlertCircle, RefreshCw, GitCommit, MessageSquare } from 'lucide-react';

interface ClinicalApprovalCardProps {
  analysisPlan: string;
  onApprove: () => void;
  onReject: (feedback: string) => void;
  isLoading?: boolean;
  isRegenerating?: boolean;
  planVersion?: number;
  feedbackHistory?: string[];
  elapsedSecs?: number;
}

export const ClinicalApprovalCard: React.FC<ClinicalApprovalCardProps> = ({
  analysisPlan,
  onApprove,
  onReject,
  isLoading = false,
  isRegenerating = false,
  planVersion = 1,
  feedbackHistory = [],
  elapsedSecs = 0,
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

  return (
    <div className={`border-2 rounded-xl p-4 sm:p-5 shadow-sm transition-all animate-fadeIn h-auto ${
      isRevised 
        ? 'bg-indigo-50/70 border-indigo-300' 
        : 'bg-amber-50/70 border-amber-300'
    }`}>
      {/* Header */}
      <div className={`flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b gap-2.5 mb-3 ${
        isRevised ? 'border-indigo-200/80' : 'border-amber-200/80'
      }`}>
        <div className="flex items-center space-x-3">
          <div className={`w-8 h-8 rounded-lg text-white flex items-center justify-center shadow-xs shrink-0 ${
            isRevised ? 'bg-indigo-600' : 'bg-amber-500'
          }`}>
            <UserCheck className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm sm:text-base font-bold text-gray-900 leading-tight tracking-tight">
                HUMAN APPROVAL
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
                ? 'Review the revised analysis plan incorporating your feedback before query compilation.'
                : 'Please review and approve the proposed analysis plan before query execution.'}
            </p>
          </div>
        </div>

        <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold self-start sm:self-auto shrink-0 border ${
          isRevised 
            ? 'bg-indigo-100 text-indigo-800 border-indigo-300' 
            : 'bg-amber-200 text-amber-900 border-amber-300'
        }`}>
          {isRevised ? 'Revised Plan Awaiting Review' : '⏳ Awaiting Approval'}
        </span>
      </div>

      {/* Applied Feedback History Callout (if revised) */}
      {feedbackHistory && feedbackHistory.length > 0 && (
        <div className="mb-3 p-2.5 bg-white/90 rounded-lg border border-indigo-200/90 text-xs">
          <div className="flex items-center space-x-1.5 font-bold text-indigo-900 mb-1">
            <MessageSquare className="w-3.5 h-3.5 text-indigo-600" />
            <span>Applied Human Corrections ({feedbackHistory.length}):</span>
          </div>
          <ul className="list-disc list-inside space-y-0.5 text-gray-700 pl-1">
            {feedbackHistory.map((item, idx) => (
              <li key={idx} className="leading-relaxed">
                <span className="font-medium text-gray-900 italic">"{item}"</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Regenerating Spinner Indicator */}
      {isRegenerating ? (
        <div className="mb-3.5 bg-white border border-indigo-200 rounded-lg p-6 flex flex-col items-center justify-center text-center shadow-inner">
          <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin mb-2" />
          <h4 className="text-xs font-bold text-gray-900">
            Regenerating Revised Analysis Plan...
          </h4>
          <p className="text-[11px] text-gray-500 mt-0.5 max-w-md">
            Analyzing your rejection feedback and updating tables, joins, aggregations, and clinical filters accordingly.
          </p>
        </div>
      ) : (
        /* Readable Analysis Plan */
        <div className="mb-3.5 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-gray-600">
              Analysis Plan
            </span>
            <span className="text-[10px] text-gray-400 font-mono">
              Deterministic Gate
            </span>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-3.5 text-xs text-gray-800 leading-relaxed font-sans max-h-56 overflow-y-auto whitespace-pre-wrap shadow-inner">
            {analysisPlan}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pt-1">
        <span className="text-[11px] text-gray-500 italic">
          {isRevised 
            ? 'You can approve this revised plan to run SQL, or reject again to provide further refinement.'
            : 'Human approval is strictly required before SQL generation.'}
        </span>

        <div className="flex items-center space-x-2.5">
          <button
            type="button"
            onClick={() => setShowFeedbackModal(true)}
            disabled={isLoading || isRegenerating}
            className="px-4 py-2 bg-white hover:bg-rose-50 hover:border-rose-300 border border-gray-300 text-gray-700 hover:text-rose-700 text-xs font-semibold rounded-lg shadow-xs transition-colors flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
          >
            <X className="w-3.5 h-3.5 text-rose-500" />
            <span>✕ Reject & Regenerate</span>
          </button>

          <button
            type="button"
            onClick={onApprove}
            disabled={isLoading || isRegenerating}
            className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-md shadow-indigo-600/20 transition-all flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Executing Pipeline{elapsedSecs > 0 ? ` (${elapsedSecs}s)` : '...'}</span>
              </>
            ) : (
              <>
                <Check className="w-3.5 h-3.5" />
                <span>✓ Approve & Continue</span>
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
            Running SQL generation &amp; AI insight pipeline
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
                {isRevised ? 'Provide Further Plan Corrections' : 'Reject Analysis Plan'}
              </h4>
            </div>
            <p className="text-xs text-gray-600 mb-4 leading-relaxed">
              Enter specific clinical or technical instructions. The system will analyze your feedback and regenerate a revised plan before stopping for your re-approval.
            </p>

            <form onSubmit={handleRejectSubmit}>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Correction Instructions (Optional):
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
                  Submit Rejection
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ClinicalApprovalCard;
