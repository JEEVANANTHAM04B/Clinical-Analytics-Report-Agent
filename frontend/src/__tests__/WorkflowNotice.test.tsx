import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { WorkflowNotice } from '../components/Clinical/WorkflowNotice';
afterEach(cleanup);
describe('Workflow failure actions', () => {
  it('shows failed stage and targeted retry/stop', () => {
    const act = vi.fn();
    render(<WorkflowNotice message="Database unavailable" recovery={{analysis_id:'run', stage_status:{stage:'execute_sql',status:'RECOVERABLE_FAILURE',allowed_actions:['retry','stop']}}} busy={false} onAction={act} onDismiss={() => {}} />);
    expect(screen.getByRole('alert').textContent).toContain('execute sql');
    fireEvent.click(screen.getByText('Retry failed stage')); expect(act).toHaveBeenCalledWith('retry');
    fireEvent.click(screen.getByText('Stop analysis')); expect(act).toHaveBeenCalledWith('stop');
  });
  it('does not offer retry for terminal validation failure', () => {
    render(<WorkflowNotice message="Invalid results" recovery={{analysis_id:'run',stage_status:{stage:'validate_results',status:'TERMINAL_FAILURE',allowed_actions:['review','stop']}}} busy={false} onAction={() => {}} onDismiss={() => {}} />);
    expect(screen.queryByText('Retry failed stage')).toBeNull();
  });
  it('shows material warnings and explicit review actions', () => {
    const act = vi.fn();
    render(<WorkflowNotice message="Review required" recovery={{analysis_id:'run',stage_status:{stage:'run_eda',status:'USER_DECISION_REQUIRED',allowed_actions:['approve_quality','reject_quality']},eda_findings:{findings:[{code:'DATE',severity:'HIGH',message:'Two dates are invalid.'}]}}} busy={false} onAction={act} onDismiss={() => {}} />);
    expect(screen.getByText('Two dates are invalid.')).toBeTruthy();
    fireEvent.click(screen.getByText('Reject and stop')); expect(act).toHaveBeenCalledWith('reject_quality');
    fireEvent.click(screen.getByText('Accept unchanged data with warnings')); expect(act).toHaveBeenCalledWith('approve_quality');
  });

  it('safely renders when eda_findings is an empty object without crashing', () => {
    const act = vi.fn();
    // This exact payload previously caused: Cannot read properties of undefined (reading 'map')
    render(
      <WorkflowNotice
        message="Insight validation failed: Highest-value claim does not match deterministic evidence."
        recovery={{
          analysis_id: undefined,
          state_version: undefined,
          stage_status: {
            stage: 'validate_insight',
            status: 'TERMINAL_FAILURE',
            allowed_actions: ['review', 'stop'],
          },
          eda_findings: {} as any,
        }}
        busy={false}
        onAction={act}
        onDismiss={() => {}}
      />
    );
    expect(screen.getByRole('alert')).toBeTruthy();
    expect(screen.getByRole('alert').textContent).toContain('validate insight');
    expect(screen.getByText('Stop analysis')).toBeTruthy();
    fireEvent.click(screen.getByText('Stop analysis'));
    expect(act).toHaveBeenCalledWith('stop');
  });

  it('safely renders when eda_findings is null or omitted', () => {
    render(
      <WorkflowNotice
        message="Pipeline failure"
        recovery={{
          stage_status: {
            stage: 'validate_insight',
            status: 'TERMINAL_FAILURE',
            allowed_actions: ['review', 'stop'],
          },
        }}
        busy={false}
        onAction={() => {}}
        onDismiss={() => {}}
      />
    );
    expect(screen.getByRole('alert').textContent).toContain('validate insight');
    expect(screen.getByText('Review details')).toBeTruthy();
  });
});
