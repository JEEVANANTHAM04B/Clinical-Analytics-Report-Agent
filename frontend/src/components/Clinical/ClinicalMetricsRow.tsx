import React from 'react';

interface ClinicalMetricsRowProps {
  totalPatients?: number | string;
  totalEncounters?: number | string;
  avgLos?: number | string;
  readmissionRate?: number | string;
  dataQualityStatus?: string;
  datasetStatus?: string;
  selectedTables?: string[];
  kpiCards?: { label: string; value: string; highlight?: boolean }[];
}

export const ClinicalMetricsRow: React.FC<ClinicalMetricsRowProps> = ({
  totalPatients = '1,171',
  totalEncounters = '53,346',
  avgLos = '1.1 Days',
  readmissionRate = '10.2%',
  dataQualityStatus = 'Fully Validated',
  datasetStatus = 'Connected',
  selectedTables,
  kpiCards,
}) => {
  const selectedTablesLabel = selectedTables && selectedTables.length > 0
    ? `${selectedTables.length} Active (${selectedTables.join(', ')})`
    : datasetStatus;

  const metrics = kpiCards && kpiCards.length > 0 ? kpiCards : [
    {
      label: 'TOTAL PATIENTS',
      value: typeof totalPatients === 'number' ? totalPatients.toLocaleString() : totalPatients,
    },
    {
      label: 'TOTAL ENCOUNTERS',
      value: typeof totalEncounters === 'number' ? totalEncounters.toLocaleString() : totalEncounters,
    },
    {
      label: 'AVG LENGTH OF STAY',
      value: typeof avgLos === 'number' ? `${avgLos} Days` : avgLos,
    },
    {
      label: '30-DAY READMISSION',
      value: typeof readmissionRate === 'number' ? `${readmissionRate}%` : readmissionRate,
    },
    {
      label: 'DATA QUALITY STATUS',
      value: dataQualityStatus,
      highlight: true,
    },
    {
      label: selectedTables ? 'SELECTED TABLES' : 'ORGANIZATION DATASET',
      value: selectedTablesLabel,
      highlight: true,
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {metrics.map((item, idx) => (
        <div
          key={idx}
          className="bg-white border border-gray-200/90 rounded-xl p-3 shadow-2xs hover:shadow-xs transition-shadow flex flex-col justify-between"
        >
          <span className="text-[9px] font-bold text-gray-400 tracking-wider uppercase block mb-1">
            {item.label}
          </span>
          <div className={`${item.label.includes('SELECTED') || item.value.length > 15 ? 'text-xs md:text-sm' : 'text-sm md:text-base'} font-extrabold text-gray-900 tracking-tight leading-snug`}>
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
};

export default ClinicalMetricsRow;
