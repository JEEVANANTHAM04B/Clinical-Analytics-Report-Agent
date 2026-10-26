import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { WorkflowNotice } from '../components/Clinical/WorkflowNotice';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { ClinicalInsightsCard } from '../components/Clinical/ClinicalInsightsCard';

afterEach(cleanup);

describe('Clinical Dashboard Error Handling & Safe Rendering', () => {
  it('7 & 9. Safe rendering after an analysis request returns HTTP 400 with backend error schema', () => {
    // Exact schema returned by backend on HTTP 400
    const backendHttp400Detail = {
      analysis_id: null,
      state_version: null,
      stage_status: {
        stage: 'validate_insight',
        status: 'TERMINAL_FAILURE',
        code: 'InsightValidationError',
        message: 'The clinical insight could not be verified against the deterministic query results.',
        recoverable: false,
        allowed_actions: ['review', 'stop'],
        retry_count: 0,
        max_retries: 2,
        user_intervention_required: true,
        next_destination: 'stop',
      },
      eda_findings: {},
      validation_attempts: [
        {
          attempt: 1,
          valid: true,
          code: 'VALID',
          correction: 'Lossless transport normalization only',
        },
      ],
      failed_node: 'validate_insight',
      exception_type: 'InsightValidationError',
      message: 'Insight failed deterministic validation: Highest-value claim does not match deterministic evidence.',
    };

    render(
      <ErrorBoundary fallbackTitle="Workspace Error">
        <WorkflowNotice
          message={backendHttp400Detail.message}
          recovery={backendHttp400Detail as any}
          busy={false}
          onAction={() => {}}
          onDismiss={() => {}}
        />
      </ErrorBoundary>
    );

    // Ensure screen did not crash to blank screen or ErrorBoundary fallback
    expect(screen.queryByText('Workspace Error')).toBeNull();
    const alert = screen.getByRole('alert');
    expect(alert).toBeTruthy();
    expect(alert.textContent).toContain('validate insight');
    expect(alert.textContent).toContain('Highest-value claim does not match deterministic evidence');
    expect(screen.getByText('Stop analysis')).toBeTruthy();
  });

  it('8. Handles eda_findings being null or missing without crashing', () => {
    render(
      <WorkflowNotice
        message="A failure occurred"
        recovery={{
          stage_status: {
            stage: 'validate_insight',
            status: 'TERMINAL_FAILURE',
            allowed_actions: ['review', 'stop'],
          },
          eda_findings: null as any,
        }}
        busy={false}
        onAction={() => {}}
        onDismiss={() => {}}
      />
    );

    expect(screen.getByRole('alert')).toBeTruthy();
    expect(screen.getByText('Stop analysis')).toBeTruthy();
  });

  it('10. Successful rendering after a fully validated analysis', () => {
    const validatedInsightText =
      'At Week 8, subjects in the Drug X treatment arm had a mean baseline hemoglobin value of 13.54 ' +
      'and a mean change of -0.80 (-5.96%). Subjects in the Placebo arm had a mean baseline of 13.50 ' +
      'and a mean change of -0.10 (-0.75%).';

    render(
      <ClinicalInsightsCard
        insight={validatedInsightText}
        keyMetric="-0.80"
        category="Drug X"
        keyFinding="Placebo"
        keyFindingValue="-0.10"
      />
    );

    expect(screen.getByText('Clinical Insights')).toBeTruthy();
    expect(screen.getByText('AI Synthesized')).toBeTruthy();
    expect(screen.getByText(/At Week 8, subjects in the Drug X treatment arm/)).toBeTruthy();
  });
});
