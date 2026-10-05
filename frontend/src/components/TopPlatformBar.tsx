import React from 'react';
import { Cloud, Undo2, Redo2, Download, Share2, Maximize2, Code2, Eye, Layout } from 'lucide-react';

interface TopPlatformBarProps {
  onDownloadReport?: () => void;
  reportReady?: boolean;
}

export const TopPlatformBar: React.FC<TopPlatformBarProps> = ({ onDownloadReport, reportReady }) => {
  return (
    <header className="h-11 bg-[#121620] border-b border-[#1E2536] px-4 flex items-center justify-between text-xs select-none sticky top-0 z-50">
      {/* Left: Platform Title and basic tools */}
      <div className="flex items-center space-x-3 text-gray-300">
        <span className="font-medium text-white tracking-tight">Clinical Analytics Platform</span>
        <div className="flex items-center space-x-2 text-gray-400 pl-2 border-l border-gray-700">
          <Cloud className="w-3.5 h-3.5 text-gray-400 hover:text-white cursor-pointer transition-colors" />
          <Undo2 className="w-3.5 h-3.5 text-gray-400 hover:text-white cursor-pointer transition-colors" />
          <Redo2 className="w-3.5 h-3.5 text-gray-400 hover:text-white cursor-pointer transition-colors" />
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center space-x-2">
        <div className="flex items-center bg-[#1C2234] rounded-md p-0.5 border border-[#2B354F]">
          <button className="flex items-center space-x-1 px-2.5 py-1 text-gray-400 hover:text-white rounded transition-colors">
            <Code2 className="w-3.5 h-3.5" />
            <span>Code</span>
          </button>
          <button className="flex items-center space-x-1 px-2.5 py-1 bg-[#2D3748] text-white font-medium rounded shadow-sm">
            <Eye className="w-3.5 h-3.5 text-indigo-400" />
            <span>Preview</span>
          </button>
        </div>

        {reportReady && onDownloadReport && (
          <button
            onClick={onDownloadReport}
            className="flex items-center space-x-1.5 px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded font-medium transition-colors shadow-sm"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download</span>
          </button>
        )}

        <div className="flex items-center space-x-2 text-gray-400 pl-1">
          <button className="p-1 hover:text-white transition-colors" title="Layout View">
            <Layout className="w-3.5 h-3.5" />
          </button>
          <button className="p-1 hover:text-white transition-colors" title="Share">
            <Share2 className="w-3.5 h-3.5" />
          </button>
          <button className="p-1 hover:text-white transition-colors" title="Fullscreen">
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </header>
  );
};

export default TopPlatformBar;
