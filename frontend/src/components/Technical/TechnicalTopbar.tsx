import React from 'react';
import { Cpu } from 'lucide-react';

interface TechnicalTopbarProps {
  title?: string;
  nodeCount?: number;
}

export const TechnicalTopbar: React.FC<TechnicalTopbarProps> = ({
  title = "Technical Observability Dashboard",
  nodeCount = 14,
}) => {
  return (
    <header className="studio-topbar h-12 bg-white border-b border-gray-200 px-5 flex items-center justify-between sticky top-0 z-40 select-none">
      {/* Title & Domain badge */}
      <div className="flex items-center space-x-2.5">
        <h1 className="text-sm font-bold text-gray-900 tracking-tight">{title}</h1>
        <span className="px-2 py-0.5 rounded-full text-[9px] font-bold tracking-wider text-blue-700 bg-blue-50 border border-blue-100 uppercase">
          DEVELOPER & AI OPS VIEW
        </span>
      </div>

      {/* LangGraph version and User badge */}
      <div className="flex items-center space-x-2.5">
        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border border-blue-200 bg-blue-50 text-[11px] font-semibold text-blue-800 shadow-2xs">
          <Cpu className="w-3 h-3 text-blue-600" />
          <span>LangGraph workflow • {nodeCount} stages</span>
        </div>

        <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-[10px] font-bold shadow-2xs">
          TA
        </div>
      </div>
    </header>
  );
};

export default TechnicalTopbar;
