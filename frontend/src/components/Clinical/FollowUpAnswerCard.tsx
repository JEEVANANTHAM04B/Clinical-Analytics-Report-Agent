import React from 'react';
import { 
  Sparkles, 
  CheckCircle2, 
  ShieldCheck, 
  X, 
  Terminal, 
  Clock, 
  Loader2,
  HelpCircle,
  ArrowRight
} from 'lucide-react';
import { FollowUpResponse } from '../../types/analytics';

export interface FollowUpHistoryItem {
  question: string;
  answer: string;
  source: string;
  sql_query?: string | null;
  verified?: boolean;
  timestamp: string;
  follow_up_results?: Record<string, any>[];
}

interface FollowUpAnswerCardProps {
  currentAnswer: FollowUpResponse | null;
  history?: FollowUpHistoryItem[];
  workspaceType?: 'clinical' | 'technical';
  isLoading?: boolean;
  onClear?: () => void;
  onRunNewAnalysis?: (question: string) => void;
}

export const FollowUpAnswerCard: React.FC<FollowUpAnswerCardProps> = ({
  currentAnswer,
  history = [],
  workspaceType = 'clinical',
  isLoading = false,
  onClear,
  onRunNewAnalysis,
}) => {
  if (!currentAnswer && !isLoading) {
    return null;
  }

  const isTechnical = workspaceType === 'technical';

  return (
    <div className="bg-white border border-indigo-100/90 rounded-xl p-4 shadow-sm space-y-3 transition-all animate-fadeIn">
      {/* Top Header */}
      <div className="flex items-center justify-between pb-2 border-b border-gray-100">
        <div className="flex items-center space-x-2">
          <div className={`w-6 h-6 rounded-lg ${isTechnical ? 'bg-blue-600' : 'bg-indigo-600'} flex items-center justify-center text-white shadow-2xs`}>
            <Sparkles className="w-3.5 h-3.5" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-gray-900 leading-tight">
              FOLLOW-UP ANSWER
            </h4>
            <span className="text-[9px] text-gray-400 block font-medium">
              Contextual Analysis Session Memory
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {isLoading ? (
            <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-100 animate-pulse">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Analyzing verified data...</span>
            </span>
          ) : currentAnswer?.is_new_analysis ? (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200">
              New Domain Inquiry
            </span>
          ) : isTechnical ? (
            <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold text-blue-700 bg-blue-50 border border-blue-200">
              <ShieldCheck className="w-3 h-3 text-emerald-600" />
              <span>
                {currentAnswer?.source === 'follow_up_sql' 
                  ? 'Safe SQL (AST Validated)' 
                  : 'Verified Results Context'}
              </span>
            </span>
          ) : (
            <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
              <span>Verified Clinical Data</span>
            </span>
          )}

          {onClear && (
            <button
              type="button"
              onClick={onClear}
              className="text-gray-400 hover:text-gray-600 p-1 rounded-md hover:bg-gray-100 transition-colors cursor-pointer"
              title="Close answer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Loading state skeleton */}
      {isLoading ? (
        <div className="py-4 space-y-2">
          <div className="h-3 bg-gray-100 rounded w-1/3 animate-pulse" />
          <div className="h-4 bg-gray-100 rounded w-5/6 animate-pulse" />
          <div className="h-4 bg-gray-100 rounded w-2/3 animate-pulse" />
        </div>
      ) : currentAnswer ? (
        <div className="space-y-2.5">
          {/* Question asked */}
          <div className="flex items-start space-x-2">
            <HelpCircle className="w-3.5 h-3.5 text-indigo-500 mt-0.5 flex-shrink-0" />
            <div className="min-w-0">
              <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
                Question
              </span>
              <p className="text-xs font-semibold text-gray-800 italic">
                "{currentAnswer.question}"
              </p>
            </div>
          </div>

          {/* Answer body */}
          <div className="bg-gray-50/90 rounded-lg p-3 border border-gray-200/80">
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-1">
              Answer
            </span>
            <p className="text-xs text-gray-800 leading-relaxed font-normal">
              {currentAnswer.answer}
            </p>

            {/* If suggested new analysis, offer primary run trigger */}
            {currentAnswer.is_new_analysis && onRunNewAnalysis && (
              <div className="mt-2.5 pt-2 border-t border-gray-200/70 flex items-center justify-between">
                <span className="text-[10px] text-gray-500">
                  Ready to launch full analysis pipeline for this domain?
                </span>
                <button
                  type="button"
                  onClick={() => onRunNewAnalysis(currentAnswer.question)}
                  className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-semibold rounded-md shadow-2xs flex items-center space-x-1 cursor-pointer transition-colors"
                >
                  <span>Launch New Analysis</span>
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            )}
          </div>

          {/* Technical visibility if Technical Workspace */}
          {isTechnical && currentAnswer.sql_query && (
            <div className="bg-[#F1F5F9] text-emerald-800 font-mono text-[10px] p-2.5 rounded-lg border border-[#E5E7EB] space-y-1">
              <div className="flex items-center justify-between text-gray-400 text-[9px] uppercase font-bold">
                <div className="flex items-center space-x-1">
                  <Terminal className="w-3 h-3 text-blue-400" />
                  <span>Executed Follow-Up SQL</span>
                </div>
                <span className="text-emerald-400 font-normal">✓ AST Safe</span>
              </div>
              <pre className="overflow-x-auto whitespace-pre-wrap py-0.5 text-gray-200">
                {currentAnswer.sql_query}
              </pre>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
};

export default FollowUpAnswerCard;
