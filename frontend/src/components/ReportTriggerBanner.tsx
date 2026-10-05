import React from 'react';
import { FileCheck2, Eye } from 'lucide-react';

interface ReportTriggerBannerProps {
  onOpenReportReview: () => void;
  title?: string;
  description?: string;
}

export const ReportTriggerBanner: React.FC<ReportTriggerBannerProps> = ({
  onOpenReportReview,
  title = "Generate Certified Technical & Clinical PDF Report",
  description = "Export a publication-ready PDF audit report containing LangGraph execution logs, AST SQL queries, clinical charts, and verified outcomes.",
}) => {
  return (
    <div className="bg-white border border-gray-200/90 rounded-xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <div className="flex items-center space-x-3">
        <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 flex-shrink-0">
          <FileCheck2 className="w-4 h-4" />
        </div>
        <div>
          <h3 className="text-xs font-bold text-gray-900 leading-tight">
            {title}
          </h3>
          <p className="text-[11px] text-gray-500 mt-0.5">
            {description}
          </p>
        </div>
      </div>

      <button
        onClick={onOpenReportReview}
        className="px-4 py-2 bg-[#4F46E5] hover:bg-[#4338CA] text-white text-xs font-semibold rounded-lg shadow-sm transition-all flex items-center justify-center space-x-1.5 cursor-pointer flex-shrink-0"
      >
        <Eye className="w-3.5 h-3.5" />
        <span>Review & Approve Report</span>
      </button>
    </div>
  );
};

export default ReportTriggerBanner;
