import React, { useState, useEffect } from 'react';
import { 
  Table2, 
  Check, 
  Loader2, 
  AlertCircle, 
  ShieldCheck 
} from 'lucide-react';
import { ClinicalTable } from '../types/analytics';
import apiService from '../services/api';

interface SidebarTableSelectorProps {
  availableTables?: ClinicalTable[];
  selectedTables: string[];
  onApplySelection: (tables: string[]) => void;
  isApplying?: boolean;
  combinationError?: string | null;
  theme?: 'technical' | 'clinical';
}

export const SidebarTableSelector: React.FC<SidebarTableSelectorProps> = ({
  availableTables = [],
  selectedTables = [],
  onApplySelection,
  isApplying = false,
  combinationError = null,
  theme = 'technical',
}) => {
  const [localSelected, setLocalSelected] = useState<string[]>(selectedTables);
  const [tables, setTables] = useState<ClinicalTable[]>(availableTables);
  const [isLoadingTables, setIsLoadingTables] = useState(false);

  // Synchronize local selection when parent selection updates
  useEffect(() => {
    setLocalSelected(selectedTables);
  }, [selectedTables]);

  // Synchronize tables with parent or self-fetch if empty
  useEffect(() => {
    if (availableTables && availableTables.length > 0) {
      setTables(availableTables);
    } else {
      setIsLoadingTables(true);
      apiService.getTables()
        .then((res: any) => {
          const list = Array.isArray(res) ? res : (res?.tables || []);
          if (list.length > 0) {
            setTables(list);
          }
        })
        .catch((err) => {
          console.error('Failed to load tables in SidebarTableSelector:', err);
        })
        .finally(() => {
          setIsLoadingTables(false);
        });
    }
  }, [availableTables]);

  const isTechnical = theme === 'technical';
  const primaryBg = isTechnical 
    ? 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800' 
    : 'bg-[#4F46E5] hover:bg-[#4338CA] active:bg-[#3730A3]';
  const checkboxColor = isTechnical ? 'text-blue-600 focus:ring-blue-500' : 'text-[#4F46E5] focus:ring-indigo-500';
  const activeItemBg = isTechnical ? 'bg-blue-50/70 border-blue-200/90' : 'bg-indigo-50/70 border-indigo-200/90';

  const toggleTable = (tableName: string) => {
    if (localSelected.includes(tableName)) {
      setLocalSelected(localSelected.filter((t) => t !== tableName));
    } else {
      setLocalSelected([...localSelected, tableName]);
    }
  };

  const handleSelectAll = () => {
    setLocalSelected(tables.map((t) => t.name));
  };

  const handleClearAll = () => {
    setLocalSelected([]);
  };

  const handleApply = () => {
    onApplySelection(localSelected);
  };

  const hasUnappliedChanges = 
    localSelected.length !== selectedTables.length || 
    localSelected.some((t) => !selectedTables.includes(t));

  return (
    <div className="mx-1.5 my-1.5 p-2 bg-gray-50/90 rounded-lg border border-gray-200/90 shadow-2xs flex flex-col space-y-1.5">
      {/* Header */}
      <div className="flex items-center justify-between pb-1 border-b border-gray-200/70">
        <div className="flex items-center space-x-1">
          <Table2 className={`w-3 h-3 ${isTechnical ? 'text-blue-600' : 'text-indigo-600'}`} />
          <span className="text-[9px] font-bold text-gray-800 uppercase tracking-wider">
            DATASET TABLES
          </span>
        </div>
        <span className="text-[9px] font-mono font-bold text-gray-600 bg-white px-1 py-0.2 rounded border border-gray-200/80 shadow-2xs">
          {localSelected.length} selected
        </span>
      </div>

      {/* Select All / Clear All quick actions */}
      <div className="flex items-center justify-between text-[9px] text-gray-500 px-0.5">
        <button
          type="button"
          onClick={handleSelectAll}
          className="hover:text-gray-900 hover:underline transition-colors cursor-pointer"
        >
          Select All
        </button>
        <span className="text-gray-300">•</span>
        <button
          type="button"
          onClick={handleClearAll}
          className="hover:text-rose-600 hover:underline transition-colors cursor-pointer"
        >
          Clear All
        </button>
      </div>

      {/* Direct Table List with Checkboxes (No inner scrolling) */}
      <div className="space-y-0.5 divide-y divide-gray-100/70">
        {isLoadingTables && tables.length === 0 ? (
          <div className="py-2 text-center text-[10px] text-gray-500 flex items-center justify-center space-x-1">
            <Loader2 className="w-3 h-3 animate-spin text-blue-600" />
            <span>Loading MySQL tables...</span>
          </div>
        ) : tables.length === 0 ? (
          <div className="py-2 text-center text-[10px] text-gray-400 italic">
            No tables available.
          </div>
        ) : (
          tables.map((tbl) => {
            const isChecked = localSelected.includes(tbl.name);
            return (
              <label
                key={tbl.name}
                onClick={() => toggleTable(tbl.name)}
                className={`flex items-center justify-between px-1.5 py-0.5 rounded cursor-pointer transition-all border ${
                  isChecked
                    ? `${activeItemBg} shadow-2xs`
                    : 'border-transparent hover:bg-gray-100/70'
                }`}
              >
                <div className="flex items-center space-x-1.5 min-w-0">
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => {}} // Controlled by row click
                    className={`w-3 h-3 rounded border-gray-300 ${checkboxColor} cursor-pointer`}
                  />
                  <span className={`text-[10px] font-mono block truncate ${isChecked ? 'font-bold text-gray-900' : 'text-gray-700'}`}>
                    {tbl.name}
                  </span>
                </div>

                <span className="text-[8px] font-mono text-gray-400 flex-shrink-0 ml-1">
                  {tbl.row_count > 999 ? `${(tbl.row_count / 1000).toFixed(0)}k` : tbl.row_count}
                </span>
              </label>
            );
          })
        )}
      </div>

      {/* Technical Relationship Status Info */}
      {isTechnical && localSelected.length > 1 && (
        <div className="pt-0.5 border-t border-gray-200/60 flex items-center justify-between text-[9px] text-gray-500">
          <div className="flex items-center space-x-1">
            <ShieldCheck className="w-2.5 h-2.5 text-emerald-600" />
            <span className="font-medium text-gray-700">Schema:</span>
          </div>
          <span className="font-mono text-emerald-700 font-bold">
            ✓ Approved
          </span>
        </div>
      )}

      {/* Combination Error Alert */}
      {combinationError && (
        <div className="p-1 rounded bg-rose-50 border border-rose-200 text-rose-700 text-[9px] leading-tight flex items-start space-x-1 shadow-2xs">
          <AlertCircle className="w-2.5 h-2.5 text-rose-500 flex-shrink-0 mt-0.5" />
          <span>{combinationError}</span>
        </div>
      )}

      {/* Apply Selection Button */}
      <button
        type="button"
        onClick={handleApply}
        disabled={isApplying || localSelected.length === 0}
        className={`w-full py-1 px-2.5 ${primaryBg} disabled:opacity-50 disabled:cursor-not-allowed text-white text-[11px] font-semibold rounded-md shadow-2xs flex items-center justify-center space-x-1 transition-all cursor-pointer`}
      >
        {isApplying ? (
          <>
            <Loader2 className="w-2.5 h-2.5 animate-spin" />
            <span>Applying...</span>
          </>
        ) : (
          <>
            <Check className="w-3 h-3 stroke-[2.5]" />
            <span>Apply Selection</span>
            {hasUnappliedChanges && (
              <span className="w-1.5 h-1.5 rounded-full bg-amber-300 animate-pulse ml-0.5" />
            )}
          </>
        )}
      </button>
    </div>
  );
};

export default SidebarTableSelector;
