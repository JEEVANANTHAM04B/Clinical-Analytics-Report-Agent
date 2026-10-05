import React from 'react';
import { Stethoscope, Code2, CheckCircle2, Shield, Layers } from 'lucide-react';

interface WorkspaceSelectionProps {
  onSelect: (workspace: 'clinical' | 'technical') => void;
}

export const WorkspaceSelection: React.FC<WorkspaceSelectionProps> = ({ onSelect }) => {
  return (
    <div className="min-h-screen bg-[#0A0E1A] flex items-center justify-center p-4 relative overflow-hidden select-none">
      {/* Background ambient lighting */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[350px] bg-indigo-600/10 rounded-full blur-[130px] pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-96 h-96 bg-blue-600/10 rounded-full blur-[100px] pointer-events-none" />

      {/* Main Container Card */}
      <div className="relative z-10 w-full max-w-4xl bg-[#111827]/95 border border-[#1F2937] rounded-2xl shadow-2xl p-8 md:p-10 backdrop-blur-sm">
        {/* Header */}
        <div className="text-center max-w-xl mx-auto mb-10">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 shadow-lg shadow-indigo-500/25 mb-4 text-white">
            <Layers className="w-6 h-6" />
          </div>
          <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
            Select Clinical Analytics Workspace
          </h1>
          <p className="mt-2 text-sm text-gray-400">
            Choose the environment tailored to your operational or technical requirements.
          </p>
        </div>

        {/* Workspace Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Clinical Analyst Card */}
          <div className="group bg-[#161F30] border border-[#243048] hover:border-indigo-500 rounded-xl p-6 transition-all duration-200 flex flex-col justify-between hover:shadow-xl hover:shadow-indigo-500/10">
            <div>
              <div className="flex items-center space-x-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 group-hover:scale-105 transition-transform">
                  <Stethoscope className="w-5 h-5 text-indigo-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white">Clinical Analyst</h3>
                  <span className="text-[11px] font-semibold text-indigo-400 tracking-wider uppercase">Domain View</span>
                </div>
              </div>

              <p className="text-xs text-gray-300 leading-relaxed mb-6">
                Designed for healthcare researchers, clinicians, and quality officers. Focused on patient outcomes, cohort metrics, and verified clinical insights without exposure to technical complexity.
              </p>

              <div className="space-y-2.5 mb-8">
                <div className="flex items-center space-x-2 text-xs text-gray-300">
                  <CheckCircle2 className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Patient Cohort & Diagnosis Analytics</span>
                </div>
                <div className="flex items-center space-x-2 text-xs text-gray-300">
                  <CheckCircle2 className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Natural Language Clinical Queries</span>
                </div>
                <div className="flex items-center space-x-2 text-xs text-gray-300">
                  <CheckCircle2 className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Medical Reference & Verified Outcomes</span>
                </div>
                <div className="flex items-center space-x-2 text-xs text-gray-300">
                  <CheckCircle2 className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Publication-Ready Report Generation</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => onSelect('clinical')}
              className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-xs font-semibold rounded-lg transition-all shadow-md shadow-indigo-600/30 flex items-center justify-center space-x-1.5 cursor-pointer"
            >
              <span>Launch Clinical Workspace</span>
              <span>→</span>
            </button>
          </div>

          {/* Technical Analyst Card */}
          <div className="group bg-[#161F30] border border-[#243048] hover:border-indigo-500 rounded-xl p-6 transition-all duration-200 flex flex-col justify-between hover:shadow-xl hover:shadow-indigo-500/10">
            <div>
              <div className="flex items-center space-x-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400 group-hover:scale-105 transition-transform">
                  <Code2 className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white">Technical Analyst</h3>
                  <span className="text-[11px] font-semibold text-indigo-400 tracking-wider uppercase">AI Ops & Observability</span>
                </div>
              </div>

              <p className="text-xs text-gray-300 leading-relaxed mb-6">
                Built for data engineers, ML researchers, and BI architects. Full observability across LangGraph state execution, AST query safety, RAG vector retrieval, and MySQL schemas.
              </p>

              <div className="space-y-2.5 mb-8">
                <div className="flex items-center space-x-2 text-xs text-gray-300">
                  <CheckCircle2 className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>LangGraph Workflow State Inspector</span>
                </div>
                <div className="flex items-center space-x-2 text-xs text-gray-300">
                  <CheckCircle2 className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>AST SQL Generation & Validation Logs</span>
                </div>
                <div className="flex items-center space-x-2 text-xs text-gray-300">
                  <CheckCircle2 className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Vector Retrieval Context & Similarity</span>
                </div>
                <div className="flex items-center space-x-2 text-xs text-gray-300">
                  <CheckCircle2 className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Human-in-the-Loop Pipeline Gating</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => onSelect('technical')}
              className="w-full py-2.5 px-4 bg-[#1E293B] hover:bg-[#2A374F] active:bg-[#1E293B] border border-gray-600 text-white text-xs font-semibold rounded-lg transition-all flex items-center justify-center space-x-1.5 cursor-pointer"
            >
              <span>Launch Technical Workspace</span>
              <span>→</span>
            </button>
          </div>
        </div>

        {/* Footer info badge */}
        <div className="mt-8 pt-6 border-t border-gray-800 text-center">
          <div className="inline-flex items-center space-x-2 text-xs text-gray-400">
            <Shield className="w-3.5 h-3.5 text-indigo-400" />
            <span>Secured RBAC • FastAPI + MySQL + LangGraph Backend</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkspaceSelection;
