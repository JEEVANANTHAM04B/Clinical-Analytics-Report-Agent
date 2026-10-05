import React, { useState } from 'react';
import { Stethoscope, Search, Loader2 } from 'lucide-react';

interface AskQuestionSectionProps {
  onRunAnalysis: (question: string) => void;
  isLoading?: boolean;
  defaultQuestion?: string;
  suggestedQuestions?: string[];
}

export const AskQuestionSection: React.FC<AskQuestionSectionProps> = ({
  onRunAnalysis,
  isLoading = false,
  defaultQuestion = 'What is the average length of stay by diagnosis?',
  suggestedQuestions,
}) => {
  const [question, setQuestion] = useState(defaultQuestion);

  // Sync internal question if defaultQuestion changes
  React.useEffect(() => {
    if (defaultQuestion) {
      setQuestion(defaultQuestion);
    }
  }, [defaultQuestion]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;
    onRunAnalysis(question.trim());
  };

  return (
    <div className="bg-white border border-gray-200/90 rounded-xl p-5 shadow-sm">
      {/* Header bar */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <Stethoscope className="w-4 h-4 text-indigo-600" />
          <span className="text-xs font-bold text-gray-700 tracking-wider uppercase">
            ASK CLINICAL QUESTION
          </span>
        </div>
        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold text-indigo-600 bg-indigo-50 border border-indigo-100">
          Clinical BI Engine
        </span>
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a clinical question (e.g., What is the average length of stay by diagnosis?)..."
            className="w-full pl-10 pr-4 py-2.5 bg-gray-50/70 border border-gray-200 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all"
            disabled={isLoading}
          />
        </div>

        <button
          type="submit"
          disabled={isLoading || !question.trim()}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-lg shadow-sm shadow-indigo-600/25 flex items-center space-x-1.5 transition-all cursor-pointer flex-shrink-0"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Analyzing...</span>
            </>
          ) : (
            <>
              <span>Run Analysis</span>
              <span>→</span>
            </>
          )}
        </button>
      </form>

      {suggestedQuestions && suggestedQuestions.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 mt-3 pt-2.5 border-t border-gray-100">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider pr-1">
            Suggested for Selected Tables:
          </span>
          {suggestedQuestions.map((sq, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setQuestion(sq);
                onRunAnalysis(sq);
              }}
              className="text-[11px] px-2.5 py-1 rounded-md bg-indigo-50/70 hover:bg-indigo-100 text-indigo-700 border border-indigo-100/90 transition-colors font-medium cursor-pointer"
            >
              {sq}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default AskQuestionSection;
