import React from 'react';
import type { AnalyticsResponse } from '../../types/analytics';

export type RecoveryAction = 'retry' | 'stop' | 'approve_quality' | 'reject_quality';
export function WorkflowNotice({message, recovery, busy, onAction, onDismiss}: {
  message: string; recovery?: Partial<AnalyticsResponse> | null; busy: boolean;
  onAction: (action: RecoveryAction) => void; onDismiss: () => void;
}) {
  const actions = recovery?.stage_status?.allowed_actions || [];
  const findings = Array.isArray(recovery?.eda_findings?.findings)
    ? recovery.eda_findings.findings
    : [];

  return <div role="alert" className="p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center justify-between">
    <div><strong>{recovery?.stage_status?.stage?.replaceAll('_', ' ') || 'Analysis'}: </strong>{message}
      {findings.map((f, i) => <p key={i}>{f.message}</p>)}
      {actions.length > 0 && <div className="flex gap-3 mt-2">
        {actions.includes('retry') && <button disabled={busy} onClick={() => onAction('retry')}>Retry failed stage</button>}
        {actions.includes('approve_quality') && <button disabled={busy} onClick={() => onAction('approve_quality')}>Accept unchanged data with warnings</button>}
        {actions.includes('reject_quality') && <button disabled={busy} onClick={() => onAction('reject_quality')}>Reject and stop</button>}
        {actions.includes('review') && <button disabled={busy} onClick={() => onDismiss()}>Review details</button>}
        {actions.includes('stop') && <button disabled={busy} onClick={() => onAction('stop')}>Stop analysis</button>}
      </div>}
    </div>
    <button aria-label="Dismiss notification" onClick={onDismiss}>×</button>
  </div>;
}
