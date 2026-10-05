import React from 'react';
import { 
  Check, 
  Clock, 
  Loader2, 
  GitBranch, 
  RotateCcw,
  X,
  RefreshCw
} from 'lucide-react';
import { PipelineNode } from '../../types/analytics';

interface PipelineVisualizerProps {
  nodes: PipelineNode[];
  onApprove?: () => void;
  onReject?: (feedback: string) => void;
  onReset?: () => void;
  onRetry?: () => void;
  isApprovalPending?: boolean;
}

const nodeDescriptions: Record<number, string> = {
  1: 'Natural language intent extraction',
  2: 'Fetching table metadata & foreign keys',
  3: 'Matching medical definitions',
  4: 'Structuring tables and joins',
  5: 'Pending analyst verification gate',
  6: 'Translating plan to optimized SQL',
  7: 'AST parsing & structural verification',
  8: 'Checking injection & destructive clauses',
  9: 'Running query in MySQL pool',
  10: 'Validating dataset dimensions',
  11: 'Auditing clinical citations',
  12: 'Synthesizing executive summary',
  13: 'Generating chart parameters',
  14: 'Packaging audit trail',
};

const defaultLatencies: Record<number, string> = {
  1: '12ms',
  2: '20ms',
  3: '45ms',
  4: '18ms',
  5: 'Interactive',
  6: '34ms',
  7: '8ms',
  8: '11ms',
  9: '42ms',
  10: '16ms',
  11: '22ms',
  12: '85ms',
  13: '14ms',
  14: '9ms',
};

export const PipelineVisualizer: React.FC<PipelineVisualizerProps> = ({
  nodes,
  onReset,
  onRetry,
  isApprovalPending = false,
}) => {
  return (
    <div className="bg-white border border-gray-200/90 rounded-xl p-4 shadow-sm flex flex-col relative">
      {/* Header matching Technical Workspace theme */}
      <div className="flex items-center justify-between pb-3 mb-2 border-b border-gray-100">
        <div className="flex items-center space-x-1.5 text-gray-800">
          <GitBranch className="w-3.5 h-3.5 text-blue-600" />
          <h3 className="text-[11px] font-bold uppercase tracking-wider">
            LANGGRAPH 14-STEP TRACE
          </h3>
        </div>

        <button
          onClick={onReset}
          className="flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium text-gray-600 bg-white hover:bg-gray-50 border border-gray-200 shadow-2xs transition-colors cursor-pointer"
        >
          <RotateCcw className="w-2.5 h-2.5 text-gray-400" />
          <span>Reset Pipeline</span>
        </button>
      </div>

      {/* Vertical 14 Steps List */}
      <div className="space-y-0 relative py-1">
        {nodes.map((node, idx) => {
          const isCompleted = node.status === 'completed';
          const isRunning = node.status === 'running';
          const isFailed = node.status === 'failed';
          const isAwaitingApproval = (node.id === 5 && isApprovalPending) || node.status === 'waiting_approval';
          const isApprovalNode = node.id === 5;
          const isLast = idx === nodes.length - 1;
          const description = nodeDescriptions[node.id] || 'Pipeline execution step';

          let latencyText = '--';
          if (isCompleted) {
            latencyText = defaultLatencies[node.id] || '12ms';
          } else if (isRunning) {
            latencyText = 'running...';
          } else if (isFailed) {
            latencyText = '✕ Failed';
          }

          return (
            <div key={node.id} className="relative flex items-start group">
              {/* Vertical connector line */}
              {!isLast && (
                <div
                  className={`absolute left-[7px] top-[14px] w-[1.5px] h-full -bottom-1 z-0 transition-colors ${
                    isCompleted ? 'bg-emerald-500' : isFailed ? 'bg-rose-300' : 'bg-gray-200'
                  }`}
                />
              )}

              {/* Status Circle Indicator */}
              <div className="relative z-10 flex-shrink-0 mr-3 mt-0.5">
                {isCompleted ? (
                  <div className="w-3.5 h-3.5 rounded-full bg-emerald-500 flex items-center justify-center text-white shadow-2xs">
                    <Check className="w-2.5 h-2.5 stroke-[3]" />
                  </div>
                ) : isFailed ? (
                  <div className="w-3.5 h-3.5 rounded-full bg-rose-500 text-white flex items-center justify-center shadow-2xs ring-2 ring-rose-200">
                    <X className="w-2.5 h-2.5 stroke-[3]" />
                  </div>
                ) : isAwaitingApproval ? (
                  <div 
                    className="w-3.5 h-3.5 rounded-full bg-amber-500 text-white flex items-center justify-center ring-2 ring-amber-300 ring-offset-1 animate-pulse shadow-xs"
                    title="Awaiting human approval"
                  >
                    <Clock className="w-2.5 h-2.5" />
                  </div>
                ) : isRunning ? (
                  <div className="w-3.5 h-3.5 rounded-full bg-blue-500 text-white flex items-center justify-center ring-2 ring-blue-300 shadow-xs">
                    <Loader2 className="w-2.5 h-2.5 animate-spin" />
                  </div>
                ) : (
                  <div className="w-3.5 h-3.5 rounded-full border-2 border-gray-300 bg-white" />
                )}
              </div>

              {/* Node Title & Description */}
              <div className="flex-1 min-w-0 pb-3">
                <div className="flex items-center justify-between">
                  <h4
                    className={`text-xs font-semibold leading-tight truncate ${
                      isFailed
                        ? 'text-rose-700 font-bold'
                        : isAwaitingApproval
                        ? 'text-amber-700 font-bold'
                        : isCompleted
                        ? 'text-gray-900'
                        : isRunning
                        ? 'text-blue-700 font-bold'
                        : 'text-gray-600'
                    }`}
                  >
                    {node.name}
                  </h4>

                  {/* Right badge: latency or status pill */}
                  {isFailed ? (
                    <div className="flex items-center space-x-1.5">
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">
                        ✕ Failed
                      </span>
                      {onRetry && (
                        <button
                          type="button"
                          onClick={onRetry}
                          className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-rose-600 hover:bg-rose-700 text-white cursor-pointer transition-colors shadow-2xs flex items-center space-x-0.5"
                        >
                          <RefreshCw className="w-2 h-2 mr-0.5" />
                          <span>Retry</span>
                        </button>
                      )}
                    </div>
                  ) : isAwaitingApproval ? (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-300 shadow-2xs flex items-center space-x-1">
                      <span>⏳ Awaiting Approval</span>
                    </span>
                  ) : isCompleted && node.id === 4 ? (
                    <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                      ✓ completed
                    </span>
                  ) : (
                    <span className="text-[10px] font-mono text-gray-400 bg-gray-50 px-1 py-0.2 rounded border border-gray-100">
                      {latencyText}
                    </span>
                  )}
                </div>

                <p className="text-[10px] text-gray-400 truncate mt-0.5 leading-tight">
                  {description}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PipelineVisualizer;
