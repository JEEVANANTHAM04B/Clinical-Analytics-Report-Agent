import React from 'react';
import { Database, UploadCloud } from 'lucide-react';

interface ActiveDatabaseCardProps {
  datasetName?: string;
  onUploadClick?: () => void;
}

export const ActiveDatabaseCard: React.FC<ActiveDatabaseCardProps> = ({
  datasetName = 'Organization EHR Dataset',
  onUploadClick,
}) => {
  return (
    <div className="bg-white border border-gray-200/90 rounded-xl p-4 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Left side info */}
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 flex-shrink-0">
            <Database className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-gray-900 leading-tight">
              Active MySQL Connection & Database Schema
            </h3>
            <p className="text-[11px] text-gray-500 mt-0.5">
              Connected database instance repository:{' '}
              <span className="text-blue-600 font-medium">{datasetName}</span>
            </p>
          </div>
        </div>

        {/* Right side status & action */}
        <div className="flex items-center space-x-2.5 flex-shrink-0">
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-[10px] font-bold">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span>Organization Dataset (Active)</span>
          </div>

          <button
            onClick={onUploadClick}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-blue-200 bg-blue-50/60 hover:bg-blue-100/70 text-blue-700 text-xs font-semibold shadow-2xs transition-colors cursor-pointer"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            <span>Upload Source Dataset / Schema File</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ActiveDatabaseCard;
