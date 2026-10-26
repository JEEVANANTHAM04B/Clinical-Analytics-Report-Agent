import React from 'react';
import { 
  Code2, 
  LayoutDashboard, 
  Activity, 
  GitFork, 
  Terminal, 
  CheckSquare, 
  History, 
  ShieldCheck, 
  Cpu, 
  Settings, 
  Stethoscope
} from 'lucide-react';
import { ClinicalTable } from '../../types/analytics';
import SidebarTableSelector from '../SidebarTableSelector';

interface TechnicalSidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  onSwitchRole: () => void;
  availableTables?: ClinicalTable[];
  selectedTables?: string[];
  onApplySelection?: (tables: string[]) => void;
  isApplying?: boolean;
  combinationError?: string | null;
}

export const TechnicalSidebar: React.FC<TechnicalSidebarProps> = ({
  activeTab,
  onTabChange,
  onSwitchRole,
  availableTables = [],
  selectedTables = [],
  onApplySelection = () => {},
  isApplying = false,
  combinationError = null,
}) => {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'analytics', label: 'Analytics', icon: Activity },
    { id: 'pipeline', label: 'Pipeline Execution', icon: GitFork },
    { id: 'sql', label: 'SQL Explorer', icon: Terminal },
    { id: 'ast', label: 'AST Validation', icon: CheckSquare },
    { id: 'queries', label: 'Query History', icon: History },
    { id: 'audit', label: 'Audit Trail', icon: ShieldCheck },
    { id: 'health', label: 'System Health', icon: Cpu },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="studio-sidebar w-56 bg-white border-r border-gray-200 flex flex-col justify-between select-none h-screen sticky top-0 flex-shrink-0 z-30">
      <div className="flex flex-col flex-1 overflow-y-auto scrollbar-thin">
        {/* Header */}
        <div className="p-2.5 border-b border-gray-100 flex items-center space-x-2 flex-shrink-0">
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm shadow-blue-600/20">
            <Code2 className="w-3.5 h-3.5" />
          </div>
          <div>
            <h2 className="text-xs font-bold text-gray-900 leading-tight">Clinical Analytics Platform</h2>
            <span className="text-[8px] font-bold text-blue-600 tracking-wider uppercase block">TECHNICAL WORKSPACE</span>
          </div>
        </div>

        {/* Navigation */}
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
                    ? 'bg-blue-50 text-blue-700 font-semibold'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-blue-600' : 'text-gray-400'}`} />
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
            theme="technical"
          />
        </div>
      </div>

      {/* Workspace switch remains available; live health is in System Health. */}
      <div className="p-2.5 border-t border-gray-100 space-y-2 flex-shrink-0 bg-white">
        <button
          onClick={onSwitchRole}
          className="w-full flex items-center justify-center space-x-1.5 py-1 px-2 border border-gray-200/90 bg-white hover:bg-gray-50 text-[11px] font-semibold text-gray-700 rounded-md shadow-2xs transition-colors cursor-pointer"
        >
          <Stethoscope className="w-3 h-3 text-gray-500" />
          <span>Return to Clinical Workspace</span>
        </button>
      </div>
    </aside>
  );
};

export default TechnicalSidebar;
