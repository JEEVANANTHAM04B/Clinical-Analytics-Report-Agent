import React, { useState } from 'react';
import { ShieldAlert, Check, X, Database, GitBranch, CheckCircle2 } from 'lucide-react';

interface TechnicalApprovalPopupProps {
  isOpen: boolean;
  onApprove: () => void;
  onReject: (feedback: string) => void;
  tables?: string[];
  strategy?: string;
  astStatus?: string;
}

export const TechnicalApprovalPopup: React.FC<TechnicalApprovalPopupProps> = ({
  isOpen,
  onApprove,
  onReject,
  tables = ['conditions', 'encounters'],
  strategy = 'AVG(DATEDIFF), GROUP BY diagnosis',
  astStatus = 'Pre-checked & Safe',
}) => {
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState('');

  if (!isOpen) return null;

  const handleRejectSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onReject(feedback);
    setShowFeedback(false);
    setFeedback('');
  };

  return (
    <div className="absolute top-full mt-3 left-1/2 -translate-x-1/2 z-50 w-96 bg-white rounded-xl shadow-2xl border-2 border-amber-400 p-4 animate-fadeIn">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 mb-3 border-b border-gray-100">
        <div className="flex items-center space-x-2">
          <ShieldAlert className="w-4 h-4 text-amber-500" />
          <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
            HUMAN APPROVAL GATE
          </h4>
        </div>
        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800">
          Pending
        </span>
      </div>

      <p className="text-[11px] text-gray-600 mb-3 leading-snug">
        Review generated analysis plan before SQL compilation.
      </p>

      {/* Technical Checks List */}
      <div className="space-y-2 bg-gray-50 p-2.5 rounded-lg border border-gray-100 mb-4 text-[11px]">
        <div className="flex items-start space-x-2">
          <Database className="w-3.5 h-3.5 text-blue-600 mt-0.5 flex-shrink-0" />
          <div>
            <span className="text-gray-500">Tables to query: </span>
            <span className="font-mono font-semibold text-gray-800">{tables.join(', ')}</span>
          </div>
        </div>

        <div className="flex items-start space-x-2">
          <GitBranch className="w-3.5 h-3.5 text-indigo-600 mt-0.5 flex-shrink-0" />
          <div>
            <span className="text-gray-500">Query strategy: </span>
            <span className="font-mono text-gray-800 text-[10px]">{strategy}</span>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
          <div>
            <span className="text-gray-500">AST Validation: </span>
            <span className="font-semibold text-emerald-700">{astStatus}</span>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end space-x-2">
        <button
          onClick={() => setShowFeedback(true)}
          className="px-3 py-1.5 bg-white hover:bg-gray-100 border border-gray-300 text-gray-700 text-xs font-semibold rounded-lg transition-colors cursor-pointer"
        >
          Reject
        </button>

        <button
          onClick={onApprove}
          className="px-4 py-1.5 bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-all flex items-center space-x-1.5 cursor-pointer"
        >
          <Check className="w-3.5 h-3.5" />
          <span>✓ Approve & Resume</span>
        </button>
      </div>

      {/* Feedback Submodal */}
      {showFeedback && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <form onSubmit={handleRejectSubmit}>
            <label className="block text-[10px] font-bold text-gray-700 uppercase mb-1">
              Rejection Reason & Plan Corrections:
            </label>
            <input
              type="text"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="e.g. Include encounters.ENCOUNTERCLASS = 'inpatient'"
              className="w-full text-xs p-2 border border-gray-300 rounded mb-2 text-gray-800"
            />
            <div className="flex justify-end space-x-1.5">
              <button
                type="button"
                onClick={() => setShowFeedback(false)}
                className="px-2 py-1 text-[11px] text-gray-500"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-3 py-1 bg-rose-600 text-white text-[11px] font-semibold rounded"
              >
                Submit Rejection
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default TechnicalApprovalPopup;
