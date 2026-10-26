import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import ReportHistory from '../components/ReportHistory';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Report History', () => {
  it('shows only reports returned by the acknowledged-history API', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => [{
      id: 'abc', title: 'Safety findings', question: 'Count events', dataset_name: 'Study A',
      generated_at: '2026-10-21T10:00:00Z', acknowledged_at: '2026-10-21T10:05:00Z', status: 'ACKNOWLEDGED',
    }] })));
    render(<ReportHistory onGenerate={() => {}} />);
    expect(await screen.findByText('Safety findings')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'View' }).getAttribute('href')).toContain('/reports/abc/pdf');
    expect(screen.getByRole('link', { name: 'Download' }).getAttribute('href')).toContain('download=true');
  });

  it('shows an empty state when there are no acknowledged reports', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => [] })));
    render(<ReportHistory onGenerate={() => {}} />);
    expect(await screen.findByText('No acknowledged reports yet')).toBeTruthy();
  });
});
