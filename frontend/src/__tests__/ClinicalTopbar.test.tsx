import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ClinicalTopbar from '../components/Clinical/ClinicalTopbar';

describe('clinical top bar', () => {
  it('provides a compact accessible control for the technical workspace', () => {
    const onOpenTechnical = vi.fn();
    render(<ClinicalTopbar onOpenTechnical={onOpenTechnical} />);

    fireEvent.click(screen.getByRole('button', { name: 'Open technical workspace' }));
    expect(onOpenTechnical).toHaveBeenCalledOnce();
    expect(screen.queryByRole('button', { name: 'Open guided clinical workflow' })).toBeNull();
  });

});
