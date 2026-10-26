import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ReportModal from '../components/ReportModal';

vi.mock('../components/PDFViewer', () => ({ PDFViewer: () => <div>PDF preview</div> }));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('Report review prerequisites', () => {
  it('does not request a PDF before an analysis has result rows', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    render(
      <ReportModal
        isOpen
        onClose={() => {}}
        question="What is the adverse event rate by treatment arm?"
        results={[]}
      />,
    );

    expect(screen.getByText('Complete an analysis to create a PDF')).toBeTruthy();
    expect(screen.queryByText('Unable to generate PDF report')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('saves the reviewed PDF only after acknowledgement and then downloads it', async () => {
    const fetchMock = vi.fn(async (url: RequestInfo | URL, _options?: RequestInit) => ({
      ok: true,
      status: 200,
      headers: new Headers({ 'X-Report-ID': 'f587b91f-fcdd-4fd9-89f9-3c7486ce9957' }),
      blob: async () => new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
      json: async () => ({ id: 'f587b91f-fcdd-4fd9-89f9-3c7486ce9957', status: 'ACKNOWLEDGED' }),
    }));
    vi.stubGlobal('fetch', fetchMock);
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:report') });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    render(<ReportModal isOpen onClose={() => {}} question="Count subjects" results={[{ subjects: 12 }]} />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(screen.getByText('PDF preview')).toBeTruthy();
    expect(String(fetchMock.mock.calls[0][0])).toContain('/analytics/report/pdf');
    expect((fetchMock.mock.calls[0][1] as RequestInit).headers).toEqual({ 'Content-Type': 'application/json' });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge Review' }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(String(fetchMock.mock.calls[1][0])).toContain('/reports/acknowledge');
    expect((fetchMock.mock.calls[1][1] as RequestInit).body).toBeInstanceOf(FormData);
    await screen.findByRole('button', { name: 'Download PDF' });
    fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }));
    await waitFor(() => expect(click).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('explains when an older authenticated server rejects PDF generation', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      json: async () => ({ detail: 'Not authenticated' }),
    })));

    render(<ReportModal isOpen onClose={() => {}} question="Count subjects" results={[{ subjects: 12 }]} />);
    expect(await screen.findByText(/Restart the updated backend on port 8001/)).toBeTruthy();
  });

  it('keeps acknowledgement pending when MySQL save fails', async () => {
    let calls = 0;
    vi.stubGlobal('fetch', vi.fn(async () => {
      calls += 1;
      if (calls === 1) return {
        ok: true,
        headers: new Headers({ 'X-Report-ID': 'f587b91f-fcdd-4fd9-89f9-3c7486ce9957' }),
        blob: async () => new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
      };
      return { ok: false, status: 503, json: async () => ({ detail: 'Could not save the acknowledged report.' }) };
    }));
    render(<ReportModal isOpen onClose={() => {}} question="Count subjects" results={[{ subjects: 12 }]} />);
    await screen.findByText('PDF preview');
    await waitFor(() => expect((screen.getByRole('button', { name: 'Acknowledge Review' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge Review' }));
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Could not save the acknowledged report.');
    expect(screen.getByRole('button', { name: 'Acknowledge Review' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Download PDF' })).toBeNull();
  });
});
