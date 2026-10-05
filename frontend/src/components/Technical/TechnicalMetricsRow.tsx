import React from 'react';

interface TechnicalMetricsRowProps {
  pipelineStatus?: string;
  astValidation?: string;
  latency?: string;
  ragScore?: string;
  sqlSafety?: string;
  mysqlPool?: string;
}

export const TechnicalMetricsRow: React.FC<TechnicalMetricsRowProps> = ({
  pipelineStatus = '14/14 Nodes',
  astValidation = '100% Pass',
  latency = '142ms',
  ragScore = '12,850 Chunks',
  sqlSafety = 'No Injection',
  mysqlPool = 'Active (4/20)',
}) => {
  const metrics = [
    {
      label: 'LANGGRAPH PIPELINE',
      value: pipelineStatus,
      borderTop: '',
      color: 'text-gray-900',
    },
    {
      label: 'AST SQL VALIDATED',
      value: astValidation,
      borderTop: '',
      color: 'text-gray-900',
    },
    {
      label: 'AVG EXECUTION LATENCY',
      value: latency,
      borderTop: '',
      color: 'text-gray-900',
    },
    {
      label: 'VECTOR EMBEDDINGS',
      value: ragScore,
      borderTop: '',
      color: 'text-gray-900',
    },
    {
      label: 'SQL SAFETY CHECK',
      value: sqlSafety,
      borderTop: 'border-t-2 border-t-emerald-500',
      color: 'text-emerald-600',
    },
    {
      label: 'MYSQL POOL STATUS',
      value: mysqlPool,
      borderTop: '',
      color: 'text-gray-900',
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {metrics.map((item, idx) => (
        <div
          key={idx}
          className={`bg-white border border-gray-200/90 rounded-xl p-3 shadow-2xs hover:shadow-xs transition-shadow flex flex-col justify-between ${
            item.borderTop || ''
          }`}
        >
          <span className="text-[9px] font-bold text-gray-400 tracking-wider uppercase block mb-1">
            {item.label}
          </span>
          <div
            className={`text-sm md:text-base font-extrabold tracking-tight leading-none ${
              item.color
            }`}
          >
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
};

export default TechnicalMetricsRow;

