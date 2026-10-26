import React, { useState, useMemo } from 'react';
import { FileCode, Copy, Check, Clock, ShieldCheck } from 'lucide-react';

interface SqlInspectorCardProps {
  sqlQuery?: string | null;
  statusBadge?: string;
}

export const formatSql = (sql: string): string => {
  if (!sql) return '';
  let clean = sql.trim().replace(/\s+/g, ' ');
  let hasSemicolon = false;
  if (clean.endsWith(';')) {
    hasSemicolon = true;
    clean = clean.slice(0, -1).trim();
  }

  // Tokenize while respecting quotes and parentheses
  const tokens: { text: string; commaAfter: boolean }[] = [];
  let current = '';
  let inSingleQuote = false;
  let inDoubleQuote = false;
  let parenDepth = 0;

  for (let i = 0; i < clean.length; i++) {
    const char = clean[i];
    if (char === '\'' && !inDoubleQuote) {
      inSingleQuote = !inSingleQuote;
      current += char;
    } else if (char === '"' && !inSingleQuote) {
      inDoubleQuote = !inDoubleQuote;
      current += char;
    } else if (!inSingleQuote && !inDoubleQuote) {
      if (char === '(') parenDepth++;
      else if (char === ')') parenDepth = Math.max(0, parenDepth - 1);

      if (parenDepth === 0 && (char === ' ' || char === ',')) {
        if (current) {
          tokens.push({ text: current, commaAfter: char === ',' });
          current = '';
        } else if (char === ',' && tokens.length > 0) {
          tokens[tokens.length - 1].commaAfter = true;
        }
      } else {
        current += char;
      }
    } else {
      current += char;
    }
  }
  if (current) tokens.push({ text: current, commaAfter: false });

  // Reconstruct clauses
  let result = '';
  let currentClause = '';
  let inBetween = false;

  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i];
    const text = token.text;
    const upper = text.toUpperCase();
    const nextText = (i + 1 < tokens.length) ? tokens[i + 1].text.toUpperCase() : '';

    // Check two-word clauses
    if (upper === 'GROUP' && nextText === 'BY') {
      result = result.trimEnd() + '\nGROUP BY ';
      currentClause = 'GROUP BY';
      i++;
      continue;
    }
    if (upper === 'ORDER' && nextText === 'BY') {
      result = result.trimEnd() + '\nORDER BY ';
      currentClause = 'ORDER BY';
      i++;
      continue;
    }
    if (['LEFT', 'RIGHT', 'INNER', 'FULL', 'CROSS'].includes(upper) && nextText === 'JOIN') {
      result = result.trimEnd() + '\n' + text + ' JOIN ';
      currentClause = 'JOIN';
      i++;
      continue;
    }
    if (upper === 'SELECT') {
      result += 'SELECT\n    ';
      currentClause = 'SELECT';
      continue;
    }
    if (upper === 'FROM') {
      result = result.trimEnd() + '\nFROM ';
      currentClause = 'FROM';
      continue;
    }
    if (upper === 'JOIN') {
      result = result.trimEnd() + '\nJOIN ';
      currentClause = 'JOIN';
      continue;
    }
    if (upper === 'WHERE') {
      result = result.trimEnd() + '\nWHERE ';
      currentClause = 'WHERE';
      inBetween = false;
      continue;
    }
    if (upper === 'HAVING') {
      result = result.trimEnd() + '\nHAVING ';
      currentClause = 'HAVING';
      inBetween = false;
      continue;
    }
    if (upper === 'LIMIT') {
      result = result.trimEnd() + '\nLIMIT ';
      currentClause = 'LIMIT';
      continue;
    }

    // Inside WHERE or HAVING
    if (currentClause === 'WHERE' || currentClause === 'HAVING') {
      if (upper === 'BETWEEN') {
        inBetween = true;
      }
      if ((upper === 'AND' || upper === 'OR') && !inBetween) {
        result = result.trimEnd() + '\n    ' + text + ' ';
        continue;
      }
      if (upper === 'AND' && inBetween) {
        // This is the AND in 'BETWEEN x AND y'
        inBetween = false;
        result += text + (token.commaAfter ? ', ' : ' ');
        continue;
      }
    }

    // Inside SELECT list
    if (currentClause === 'SELECT') {
      result += text;
      if (token.commaAfter) {
        result += ',\n    ';
      } else {
        result += ' ';
      }
      continue;
    }

    // Other tokens
    result += text + (token.commaAfter ? ', ' : ' ');
  }

  let finalSql = result.trim();
  if (hasSemicolon || !finalSql.endsWith(';')) {
    finalSql += ';';
  }
  return finalSql;
};

export const SqlInspectorCard: React.FC<SqlInspectorCardProps> = ({
  sqlQuery,
  statusBadge = 'Awaiting Approval',
}) => {
  const [copied, setCopied] = useState(false);

  const defaultSampleSql = `SELECT
    c.diagnosis,
    AVG(DATEDIFF(e.stop, e.start)) AS average_length_of_stay
FROM conditions c
JOIN encounters e ON c.encounter = e.id
WHERE e.encounterclass = 'inpatient'
    AND DATEDIFF(e.stop, e.start) BETWEEN 0 AND 30
GROUP BY c.diagnosis
ORDER BY average_length_of_stay DESC;`;

  const formattedDisplaySql = useMemo(() => {
    return sqlQuery ? formatSql(sqlQuery) : defaultSampleSql;
  }, [sqlQuery, defaultSampleSql]);

  const isAwaiting = !sqlQuery || statusBadge.toLowerCase().includes('awaiting');

  const handleCopy = () => {
    navigator.clipboard.writeText(formattedDisplaySql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const renderHighlightedSql = (rawSql: string) => {
    const lines = rawSql.split('\n');
    return (
      <>
        {lines.map((line, lIdx) => {
          const parts = line.split(/(\b(?:SELECT|FROM|JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|ON|WHERE|AND|OR|GROUP\s+BY|ORDER\s+BY|LIMIT|BETWEEN|IN|IS|NOT|NULL|AS|DESC|ASC)\b|\b(?:AVG|COUNT|SUM|MIN|MAX|DATEDIFF|ROUND|DATE_FORMAT|DISTINCT)\b|'[^']*'|"[^"]*"|\b\d+\b)/gi);
          return (
            <div key={lIdx}>
              {parts.map((part, pIdx) => {
                const upper = part.toUpperCase().trim();
                if (['SELECT', 'FROM', 'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'ON', 'WHERE', 'AND', 'OR', 'GROUP BY', 'ORDER BY', 'LIMIT', 'BETWEEN', 'IN', 'IS', 'NOT', 'NULL', 'AS', 'DESC', 'ASC'].includes(upper)) {
                  return <span key={pIdx} className="text-[#EC4899] font-bold">{part}</span>;
                }
                if (['AVG', 'COUNT', 'SUM', 'MIN', 'MAX', 'DATEDIFF', 'ROUND', 'DATE_FORMAT', 'DISTINCT'].includes(upper)) {
                  return <span key={pIdx} className="text-[#38BDF8] font-semibold">{part}</span>;
                }
                if ((part.startsWith("'") && part.endsWith("'")) || (part.startsWith('"') && part.endsWith('"'))) {
                  return <span key={pIdx} className="text-[#34D399]">{part}</span>;
                }
                if (/^\d+$/.test(part.trim())) {
                  return <span key={pIdx} className="text-[#F59E0B]">{part}</span>;
                }
                return <span key={pIdx}>{part}</span>;
              })}
            </div>
          );
        })}
      </>
    );
  };

  return (
    <div className="bg-white border border-gray-200/90 rounded-xl p-4 shadow-sm space-y-2.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <FileCode className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-bold text-gray-900 leading-tight">
            Generated SQL & AST Inspection
          </h3>
        </div>

        <div className="flex items-center space-x-2">
          <span
            className={`flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold border ${
              isAwaiting
                ? 'text-amber-800 bg-amber-50 border-amber-200'
                : 'text-emerald-700 bg-emerald-50 border border-emerald-200'
            }`}
          >
            {isAwaiting ? (
              <>
                <Clock className="w-3 h-3 text-amber-600" />
                <span>Awaiting Approval</span>
              </>
            ) : (
              <>
                <ShieldCheck className="w-3 h-3 text-emerald-600" />
                <span>AST Validated</span>
              </>
            )}
          </span>

          <button
            onClick={handleCopy}
            className="flex items-center space-x-1 px-2.5 py-1 rounded-md border border-gray-200 bg-white hover:bg-gray-50 text-[11px] font-medium text-gray-700 shadow-2xs transition-colors cursor-pointer"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 text-emerald-600" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-4 text-gray-400" />
                <span>Copy SQL</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Code Editor Box */}
      <div className="bg-[#F1F5F9] text-[#111827] font-mono text-[11px] p-3.5 rounded-lg border border-[#E5E7EB] leading-relaxed overflow-x-auto">
        <pre className="whitespace-pre-wrap font-mono">
          {!sqlQuery ? (
            <span className="text-gray-500">
              -- Trigger execution to compile AST-optimized SQL query
            </span>
          ) : (
            renderHighlightedSql(formattedDisplaySql)
          )}
        </pre>
      </div>
    </div>
  );
};

export default SqlInspectorCard;


