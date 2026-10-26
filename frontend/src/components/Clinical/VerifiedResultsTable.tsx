import React from 'react';
import { Database, CheckCircle2 } from 'lucide-react';

interface VerifiedResultsTableProps {
  results?: Record<string, any>[];
  badgeText?: string;
  title?: string;
}

export const VerifiedResultsTable: React.FC<VerifiedResultsTableProps> = ({
  results = [],
  badgeText,
  title = 'Verified Results',
}) => {
  const displayRows = results || [];

  const countBadge = badgeText || (displayRows.length > 0 ? `${displayRows.length} Rows Verified` : 'No result rows');

  // Dynamically inspect column names
  const firstItem = displayRows[0] || {};
  const keys = Object.keys(firstItem);
  const diagCol = keys.find((k) => /diag|desc|name|condition|class|term|arm/i.test(k)) || keys[0] || 'diagnosis';
  const valCol = keys.find((k) => /avg|los|day|count|rate|pct|val/i.test(k) && k !== diagCol) || keys.find((k) => k !== diagCol) || 'value';
  const label = (key: string) => key === 'average_length_of_stay'
    ? 'Avg. stay (days)'
    : key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  const formatValue = (value: unknown) => {
    if (value == null) return '—';
    if (typeof value !== 'number') return String(value);
    if (/los|length_of_stay|days?/i.test(valCol)) return `${value.toFixed(1)} days`;
    if (/pct|percent/i.test(valCol)) return `${value.toLocaleString()}%`;
    return value.toLocaleString();
  };

  return (
    <div data-testid="verified-results-table" className="studio-results-card bg-white border border-gray-200/90 rounded-xl p-3.5 shadow-sm flex flex-col justify-between h-full">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-gray-100">
          <div className="flex items-center space-x-1.5">
            <Database className="w-3.5 h-3.5 text-emerald-600" />
            <h3 className="text-xs font-bold text-gray-900">{title}</h3>
          </div>
          <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100">
            <span data-testid="verified-results-badge">{countBadge}</span>
          </span>
        </div>

        {/* Clean Formatted Table */}
        <div className="overflow-x-auto max-h-[160px] overflow-y-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50/70 text-left text-[10px] font-bold text-gray-500 uppercase tracking-wider">
                <th className="py-1.5 px-2 font-semibold">{displayRows.length ? label(diagCol) : 'Category'}</th>
                <th className="py-1.5 px-2 font-semibold text-right">{displayRows.length ? label(valCol) : 'Value'}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {displayRows.map((row, idx) => {
                const diagVal = String(row[diagCol] ?? row.diagnosis ?? '');
                const numVal = formatValue(row[valCol]);

                return (
                  <tr key={idx} className="hover:bg-indigo-50/30 transition-colors">
                    <td className="py-1.5 px-2 text-gray-800 font-medium truncate max-w-[170px] text-[11px]">
                      {diagVal}
                    </td>
                    <td className="py-1.5 px-2 text-right font-mono font-bold text-indigo-600 text-[11px]">
                      {numVal}
                    </td>
                  </tr>
                );
              })}
              {displayRows.length === 0 && (
                <tr><td colSpan={2} className="px-2 py-6 text-center text-gray-500">No verified result rows yet. Run an analysis to populate this table.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default VerifiedResultsTable;
