import React, { useState } from 'react';
import { Bookmark, Search, Zap, Loader2 } from 'lucide-react';

interface FollowUpSectionProps {
  onAskFollowUp: (question: string) => void;
  isLoading?: boolean;
}

const defaultSuggested = [
  'Which diagnosis has the highest average length of stay?',
  'Why is Anemia higher than the other diagnoses?',
  'How many diagnoses have an average stay above 2 days?',
];

export const FollowUpSection: React.FC<FollowUpSectionProps> = ({
  onAskFollowUp,
  isLoading = false,
}) => {
  const [question, setQuestion] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;
    onAskFollowUp(question.trim());
    setQuestion('');
  };

  const handleChipClick = (chipText: string) => {
    if (isLoading) return;
    setQuestion(chipText);
    onAskFollowUp(chipText);
  };

  return (
    <div className="bg-white border border-gray-200/90 rounded-xl p-4 shadow-sm space-y-3">
      {/* Header matching Screenshot 1 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2 text-[#4F46E5]">
          <Bookmark className="w-4 h-4" />
          <h3 className="text-xs font-bold text-gray-900 leading-tight">
            Follow-Up Analysis & Next Queries
          </h3>
        </div>

        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold text-[#4F46E5] bg-[#EEF2FF] border border-[#C7D2FE]">
          Interactive AI
        </span>
      </div>

      <p className="text-[11px] text-gray-500">
        Ask a follow-up question regarding patient length of stay, diagnoses, or readmission metrics:
      </p>

      {/* Input bar */}
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Filter results for patients over 65 years old..."
            className="w-full pl-9 pr-3 py-2 text-xs bg-white border border-gray-200 rounded-lg text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={isLoading}
          />
        </div>

        <button
          type="submit"
          disabled={isLoading || !question.trim()}
          className="px-4 py-2 bg-[#4F46E5] hover:bg-[#4338CA] disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-sm flex items-center space-x-1.5 transition-colors cursor-pointer flex-shrink-0"
        >
          {isLoading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <>
              <Zap className="w-3 h-3" />
              <span>Run Follow-up</span>
            </>
          )}
        </button>
      </form>

      {/* Suggested Quick Query Chips */}
      <div className="flex items-center flex-wrap gap-2 pt-1">
        {defaultSuggested.map((chip, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => handleChipClick(chip)}
            disabled={isLoading}
            className="text-[10px] px-2.5 py-1 rounded-md bg-gray-50 hover:bg-gray-100 text-gray-700 border border-gray-200 shadow-2xs transition-colors cursor-pointer font-medium"
          >
            "{chip}"
          </button>
        ))}
      </div>
    </div>
  );
};

export default FollowUpSection;


