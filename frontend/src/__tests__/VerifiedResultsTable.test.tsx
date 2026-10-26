import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import VerifiedResultsTable from '../components/Clinical/VerifiedResultsTable';

describe('verified results presentation', () => {
  it('labels and formats real count values without adding a time unit', () => {
    render(<VerifiedResultsTable results={[{ diagnosis: 'Headache', count: 2571 }]} />);
    expect(screen.getByRole('columnheader', { name: 'Count' })).toBeTruthy();
    expect(screen.getByRole('cell', { name: '2,571' })).toBeTruthy();
  });

  it('shows an empty state instead of sample clinical rows', () => {
    render(<VerifiedResultsTable results={[]} />);
    expect(screen.getByText(/No verified result rows yet/)).toBeTruthy();
    expect(screen.queryByText('Cardiovascular Disease')).toBeNull();
  });
});
