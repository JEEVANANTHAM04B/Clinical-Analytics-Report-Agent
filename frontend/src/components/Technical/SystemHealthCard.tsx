import React from 'react';
import { Cpu, CheckCircle2 } from 'lucide-react';

export const SystemHealthCard: React.FC = () => {
  const components = [
    {
      name: 'FastAPI Backend Service',
      latency: '12ms',
      status: 'Healthy',
      color: 'text-emerald-600',
    },
    {
      name: 'MySQL Production Pool',
      latency: '4ms',
      status: 'Healthy',
      color: 'text-emerald-600',
    },
    {
      name: 'LangGraph State Engine',
      latency: '8ms',
      status: 'Active',
      color: 'text-blue-600',
    },
    {
      name: 'RAG Retriever & Vector Store',
      latency: '35ms',
      status: 'Synced',
      color: 'text-emerald-600',
    },
  ];

  return (
    <div className="bg-white border border-gray-200/90 rounded-xl p-5 shadow-sm">
      <div className="flex items-center space-x-2 mb-4">
        <Cpu className="w-4 h-4 text-blue-600" />
        <h3 className="text-sm font-bold text-gray-900">System Component Health</h3>
      </div>

      <div className="space-y-2.5">
        {components.map((comp, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between p-2.5 bg-gray-50 border border-gray-100 rounded-lg text-xs"
          >
            <div className="flex items-center space-x-2.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-semibold text-gray-800">{comp.name}</span>
            </div>

            <div className="flex items-center space-x-4 font-mono text-[11px]">
              <span className="text-gray-400">Latency: {comp.latency}</span>
              <span className={`font-bold ${comp.color}`}>{comp.status}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SystemHealthCard;
