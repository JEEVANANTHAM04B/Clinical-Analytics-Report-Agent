import React from 'react';
import { 
  Stethoscope, 
  LayoutDashboard, 
  Activity, 
  MessageSquare, 
  TrendingUp, 
  History, 
  FileText, 
  Settings
} from 'lucide-react';

import { ClinicalTable } from '../../types/analytics';
import SidebarTableSelector from '../SidebarTableSelector';

interface ClinicalSidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  availableTables?: ClinicalTable[];
  selectedTables?: string[];
  onApplySelection?: (tables: string[]) => void;
  isApplying?: boolean;
  combinationError?: string | null;
}

export const ClinicalSidebar: React.FC<ClinicalSidebarProps> = ({
  activeTab,
  onTabChange,
  availableTables = [],
  selectedTables = [],
  onApplySelection = () => {},
  isApplying = false,
  combinationError = null,
}) => {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'analytics', label: 'Clinical Analytics', icon: Activity },
    { id: 'queries', label: 'Questions & Queries', icon: MessageSquare },
    { id: 'trends', label: 'Patient Trends', icon: TrendingUp },
    { id: 'history', label: 'Analysis History', icon: History },
    { id: 'reports', label: 'Clinical Reports', icon: FileText },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="studio-sidebar w-56 bg-white border-r border-gray-200 flex flex-col justify-between select-none h-screen sticky top-0 flex-shrink-0 z-30">
      <div className="flex flex-col flex-1 overflow-y-auto scrollbar-thin">
        {/* Brand header */}
        <div className="p-2.5 border-b border-gray-100 flex items-center space-x-2 flex-shrink-0">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-sm shadow-indigo-600/20">
            <Stethoscope className="w-3.5 h-3.5" />
          </div>
          <div>
            <h2 className="text-xs font-bold text-gray-900 leading-tight">Clinical Analytics Platform</h2>
            <span className="text-[8px] font-bold text-indigo-600 tracking-wider uppercase block">CLINICAL WORKSPACE</span>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="p-1.5 space-y-0.5">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                aria-current={isActive ? 'page' : undefined}
                className={`studio-nav-item w-full flex items-center space-x-2 px-2 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700 font-semibold'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-indigo-600' : 'text-gray-400'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* DATASET TABLE SELECTION (Exact Red-Box Empty Sidebar Area) */}
        <div className="border-t border-gray-100 pt-0.5">
          <SidebarTableSelector
            availableTables={availableTables}
            selectedTables={selectedTables}
            onApplySelection={onApplySelection}
            isApplying={isApplying}
            combinationError={combinationError}
            theme="clinical"
          />
        </div>
      </div>

    </aside>
  );
};

export default ClinicalSidebar;
