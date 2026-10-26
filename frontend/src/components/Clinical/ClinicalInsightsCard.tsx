import React from 'react';
import { Sparkles, CheckCircle2 } from 'lucide-react';

interface ClinicalInsightsCardProps {
  insight?: string | null;
  keyMetric?: string;
  category?: string;
  keyFinding?: string;
  keyFindingValue?: string;
}

export const ClinicalInsightsCard: React.FC<ClinicalInsightsCardProps> = ({
  insight,
  keyMetric = '—',
  category = 'No verified finding',
  keyFinding,
  keyFindingValue,
}) => {
  const displayMetric = keyFindingValue || keyMetric;
  const displayCategory = keyFinding || category;

  // Parse insight into clean readable bullet points or fallback to structured points
  const rawText = insight || '';
  
  // Extract bullet points if already formatted with asterisks/bullets, or split by sentence
  const extractedBullets = rawText
    .split(/\n|\. /)
    .map((s) => s.replace(/^[\*\-\•]\s*/, '').trim())
    .filter((s) => s.length > 15 && !s.toLowerCase().includes('based on the verified'));

  const findings = extractedBullets.slice(0, 3);

  // If no specific insight, show the concise overview message from Screenshot 1 & 3
  const isOverview = !insight;

  return (
    <div className="studio-insight-card bg-white border border-gray-200/90 rounded-xl p-3.5 shadow-sm flex flex-col justify-between h-full">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-gray-100">
          <div className="flex items-center space-x-1.5">
            <Sparkles className="w-3.5 h-3.5 text-[#4F46E5]" />
            <h3 className="text-xs font-bold text-gray-900">Clinical Insights</h3>
          </div>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold text-[#4F46E5] bg-[#EEF2FF] border border-[#C7D2FE]">
            AI Synthesized
          </span>
        </div>

        {/* Content */}
        {isOverview ? (
          <p className="text-[11px] text-gray-600 leading-relaxed pt-1">
            General clinical overview active. Run a clinical query above to inspect targeted patient diagnosis metrics and outcomes.
          </p>
        ) : (
          findings.length ? <div className="space-y-1.5 pt-1">
            <ul className="space-y-1 text-[11px] text-gray-700">
              {findings.map((finding, idx) => (
                <li key={idx} className="flex items-start space-x-1.5">
                  <CheckCircle2 className="w-3 h-3 text-[#4F46E5] mt-0.5 flex-shrink-0" />
                  <span className="leading-snug">{finding}</span>
                </li>
              ))}
            </ul>
          </div> : <p className="text-[11px] text-gray-600 leading-relaxed pt-1">
            No validated insight is available for this analysis.
          </p>
        )}
      </div>

      {/* Structured Key Clinical Finding Box matching Screenshot 1 & 3 */}
      <div className="mt-3 pt-2 border-t border-gray-100">
        <div className="bg-[#EEF2FF]/40 border border-[#C7D2FE]/70 rounded-lg p-2.5 flex items-center justify-between">
          <div>
            <span className="text-[8px] font-bold text-gray-400 uppercase tracking-wider block">
              KEY CLINICAL FINDING
            </span>
            <span className="text-xs font-bold text-gray-800">
              {displayCategory}
            </span>
          </div>
          <span className="text-xs md:text-sm font-extrabold text-[#4F46E5] font-mono">
            {displayMetric}
          </span>
        </div>
      </div>
    </div>
  );
};

export default ClinicalInsightsCard;
