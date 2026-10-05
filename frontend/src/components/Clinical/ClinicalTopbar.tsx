import React from 'react';
import { Database } from 'lucide-react';

interface ClinicalTopbarProps {
  title?: string;
  datasetName?: string;
}

export const ClinicalTopbar: React.FC<ClinicalTopbarProps> = ({
  title = "Clinical Dashboard",
  datasetName = "Organization Dataset"
}) => {
  return (
    <header className="h-12 bg-white border-b border-gray-200 px-5 flex items-center justify-between sticky top-0 z-40 select-none">
      {/* Title & Domain badge */}
      <div className="flex items-center space-x-2.5">
        <h1 className="text-sm font-bold text-gray-900 tracking-tight">{title}</h1>
        <span className="px-2 py-0.5 rounded-full text-[9px] font-bold tracking-wider text-indigo-700 bg-indigo-50 border border-indigo-100 uppercase">
          CLINICAL DOMAIN VIEW
        </span>
      </div>

      {/* Dataset & Profile */}
      <div className="flex items-center space-x-2.5">
        <button className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-[11px] font-medium text-gray-700 shadow-2xs transition-colors">
          <Database className="w-3 h-3 text-indigo-600" />
          <span>{datasetName}</span>
        </button>

        <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-white text-[10px] font-bold shadow-2xs">
          CA
        </div>
      </div>
    </header>
  );
};

export default ClinicalTopbar;
