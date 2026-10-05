import React, { useState, useRef, useEffect } from 'react';
import { 
  Table2, 
  ChevronDown, 
  Check, 
  X, 
  AlertTriangle, 
  Loader2, 
  Sparkles,
  Layers,
  Database
} from 'lucide-react';
import { ClinicalTable } from '../types/analytics';

interface TableSelectorPopoverProps {
  availableTables: ClinicalTable[];
  selectedTables: string[];
  onChangeSelected: (tables: string[]) => void;
  onApply: (tables: string[]) => void;
  isApplying?: boolean;
  combinationError?: string | null;
  theme?: 'clinical' | 'technical';
}

export const TableSelectorPopover: React.FC<TableSelectorPopoverProps> = ({
  availableTables = [],
  selectedTables = [],
  onChangeSelected,
  onApply,
  isApplying = false,
  combinationError = null,
  theme = 'clinical',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const isTechnical = theme === 'technical';
  const primaryBg = isTechnical ? 'bg-blue-600 hover:bg-blue-700' : 'bg-[#4F46E5] hover:bg-[#4338CA]';
  const accentText = isTechnical ? 'text-blue-600' : 'text-[#4F46E5]';
  const accentBorder = isTechnical ? 'border-blue-200' : 'border-indigo-200';
  const accentLightBg = isTechnical ? 'bg-blue-50/70' : 'bg-indigo-50/70';

  const toggleTable = (tableName: string) => {
    if (selectedTables.includes(tableName)) {
      onChangeSelected(selectedTables.filter((t) => t !== tableName));
    } else {
      onChangeSelected([...selectedTables, tableName]);
    }
  };

  const removeChip = (tableName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onChangeSelected(selectedTables.filter((t) => t !== tableName));
  };

  const selectAll = () => {
    onChangeSelected(availableTables.map((t) => t.name));
  };

  const clearAll = () => {
    onChangeSelected([]);
  };

  const handleApply = () => {
    setIsOpen(false);
    onApply(selectedTables);
  };

  const filteredTables = availableTables.filter((t) =>
    t.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.display_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="relative w-full" ref={popoverRef}>
      {/* Top Container: Trigger Button + Chips + Apply Button */}
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-2 flex-1 min-w-0">
          {/* Popover Trigger Button */}
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg border ${accentBorder} ${accentLightBg} text-xs font-semibold ${accentText} shadow-2xs hover:shadow-xs transition-all cursor-pointer flex-shrink-0`}
          >
            <Table2 className="w-3.5 h-3.5" />
            <span>Select Data Tables</span>
            {selectedTables.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-white text-gray-700 border border-gray-200 shadow-2xs">
                {selectedTables.length}
              </span>
            )}
            <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
          </button>

          {/* Chips of Currently Selected Tables */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider pl-1">
              Selected:
            </span>
            {selectedTables.length === 0 ? (
              <span className="text-xs text-gray-400 italic">
                None selected (click to select tables)
              </span>
            ) : (
              selectedTables.map((tbl) => (
                <span
                  key={tbl}
                  className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-gray-100/90 text-gray-800 border border-gray-200/90 shadow-2xs hover:bg-gray-200/80 transition-colors"
                >
                  <span className="font-mono">{tbl}</span>
                  <button
                    type="button"
                    onClick={(e) => removeChip(tbl, e)}
                    className="hover:text-rose-600 text-gray-400 transition-colors cursor-pointer ml-0.5"
                    title={`Remove ${tbl}`}
                  >
                    <X className="w-3 h-3 stroke-[2.5]" />
                  </button>
                </span>
              ))
            )}
          </div>
        </div>

        {/* Right side Apply Button */}
        <div className="flex items-center space-x-2 flex-shrink-0">
          <button
            type="button"
            onClick={handleApply}
            disabled={isApplying || selectedTables.length === 0}
            className={`flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg ${primaryBg} disabled:opacity-50 text-white text-xs font-semibold shadow-2xs transition-all cursor-pointer`}
          >
            {isApplying ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Applying...</span>
              </>
            ) : (
              <>
                <Check className="w-3.5 h-3.5 stroke-[2.5]" />
                <span>Apply Selection</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Relationship Combination Error Alert */}
      {combinationError && (
        <div className="mt-2.5 p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center space-x-2 shadow-2xs animate-fadeIn">
          <AlertTriangle className="w-4 h-4 text-rose-500 flex-shrink-0" />
          <span className="font-medium">{combinationError}</span>
        </div>
      )}

      {/* Floating Dropdown / Popover */}
      {isOpen && (
        <div className="absolute left-0 top-full mt-2 w-full max-w-md bg-white border border-gray-200/90 rounded-xl shadow-xl z-50 p-3 space-y-2.5 animate-scaleIn backdrop-blur-md">
          {/* Header */}
          <div className="flex items-center justify-between pb-2 border-b border-gray-100">
            <div className="flex items-center space-x-1.5">
              <Database className="w-3.5 h-3.5 text-gray-600" />
              <h4 className="text-xs font-bold text-gray-900">
                Available MySQL Clinical Tables
              </h4>
            </div>
            <span className="text-[10px] font-mono text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100">
              {availableTables.length} Tables Loaded
            </span>
          </div>

          {/* Quick Search */}
          {availableTables.length > 5 && (
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Filter tables..."
              className="w-full px-2.5 py-1 text-xs border border-gray-200 rounded-md bg-gray-50/70 text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          )}

          {/* Checkboxes List */}
          <div className="max-h-52 overflow-y-auto space-y-1 pr-1 divide-y divide-gray-50">
            {filteredTables.map((tbl) => {
              const isChecked = selectedTables.includes(tbl.name);
              return (
                <label
                  key={tbl.name}
                  onClick={() => toggleTable(tbl.name)}
                  className={`flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors ${
                    isChecked
                      ? isTechnical
                        ? 'bg-blue-50/60 border border-blue-100'
                        : 'bg-indigo-50/60 border border-indigo-100'
                      : 'hover:bg-gray-50/80 border border-transparent'
                  }`}
                >
                  <div className="flex items-center space-x-2.5 min-w-0">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => {}} // Controlled via label click
                      className={`w-3.5 h-3.5 rounded border-gray-300 ${
                        isTechnical ? 'text-blue-600 focus:ring-blue-500' : 'text-[#4F46E5] focus:ring-indigo-500'
                      }`}
                    />
                    <div className="min-w-0">
                      <span className="text-xs font-semibold text-gray-800 font-mono block truncate">
                        {tbl.name}
                      </span>
                      <span className="text-[10px] text-gray-400 block truncate">
                        {tbl.columns.length} columns available
                      </span>
                    </div>
                  </div>

                  <span className="text-[11px] font-mono font-medium text-gray-500 bg-white px-2 py-0.5 rounded border border-gray-100 shadow-2xs">
                    {tbl.row_count.toLocaleString()} rows
                  </span>
                </label>
              );
            })}
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-between pt-2 border-t border-gray-100 text-xs">
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={selectAll}
                className="text-[11px] font-medium text-gray-600 hover:text-gray-900 transition-colors cursor-pointer hover:underline"
              >
                Select All
              </button>
              <span className="text-gray-300">•</span>
              <button
                type="button"
                onClick={clearAll}
                className="text-[11px] font-medium text-gray-600 hover:text-rose-600 transition-colors cursor-pointer hover:underline"
              >
                Clear All
              </button>
            </div>

            <button
              type="button"
              onClick={handleApply}
              disabled={isApplying || selectedTables.length === 0}
              className={`px-3 py-1 rounded-md ${primaryBg} disabled:opacity-50 text-white text-xs font-semibold shadow-2xs transition-colors cursor-pointer`}
            >
              Apply Selection
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default TableSelectorPopover;
