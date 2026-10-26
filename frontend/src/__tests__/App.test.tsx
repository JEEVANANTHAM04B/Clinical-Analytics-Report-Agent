import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../App';

vi.mock('../pages/ClinicalDashboard', () => ({
  default: ({ onSwitchRole }: { onSwitchRole: () => void }) => (
    <main>
      <h1>Clinical workspace</h1>
      <button aria-label="Open technical workspace" onClick={onSwitchRole}>Technical tools</button>
    </main>
  ),
}));

vi.mock('../pages/TechnicalDashboard', () => ({
  default: ({ onSwitchRole }: { onSwitchRole: () => void }) => (
    <main>
      <h1>Technical workspace</h1>
      <button onClick={onSwitchRole}>Return to clinical workspace</button>
    </main>
  ),
}));

afterEach(() => {
  vi.clearAllMocks();
});

describe('workspace entry and switching', () => {
  it('opens the clinical workspace first and exposes technical tools through its icon action', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Clinical workspace' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Open technical workspace' }));
    expect(await screen.findByRole('heading', { name: 'Technical workspace' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Return to clinical workspace' }));
    expect(await screen.findByRole('heading', { name: 'Clinical workspace' })).toBeTruthy();
  });
});
