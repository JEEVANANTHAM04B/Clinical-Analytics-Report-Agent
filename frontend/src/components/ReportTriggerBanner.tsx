import React from 'react';
import { FileCheck2, Eye } from 'lucide-react';

interface ReportTriggerBannerProps {
  onOpenReportReview: () => void;
  title?: string;
  description?: string;
}

export const ReportTriggerBanner: React.FC<ReportTriggerBannerProps> = ({
  onOpenReportReview,
  title = "Generate Clinical PDF Report",
  description = "Review and export a clinical analytics report with results, charts, interpretation, and traceability.",
}) => {
  return (
    <div className="bg-white border border-[#E5E7EB] rounded-xl p-5 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div className="flex items-center space-x-4">
        <div className="w-11 h-11 rounded-lg bg-[#EEF2FF] border border-[#C7D2FE] flex items-center justify-center text-[#4F46E5] flex-shrink-0">
          <FileCheck2 className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-lg font-semibold tracking-tight text-[#111827] leading-tight">
            {title}
          </h3>
          <p className="text-sm text-[#64748B] mt-1 leading-relaxed">
            {description}
          </p>
        </div>
      </div>

      <button
        onClick={onOpenReportReview}
        className="px-5 py-3 bg-[#4F46E5] hover:bg-[#4338CA] text-white text-sm font-semibold rounded-lg shadow-sm transition-all flex items-center justify-center space-x-2 cursor-pointer flex-shrink-0"
      >
        <Eye className="w-4 h-4" />
        <span>Review & Approve Report</span>
      </button>
    </div>
  );
};

export default ReportTriggerBanner;
