import React, { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

import {
  SidebarTableSelector,
  APPROVED_CLINICAL_TABLES,
  LEGACY_EHR_TABLES,
  filterApprovedClinicalTables,
  getAvailableClinicalTableNames,
} from '../components/SidebarTableSelector';
import ClinicalMetricsRow from '../components/Clinical/ClinicalMetricsRow';
import { ClinicalTable } from '../types/analytics';

const MOCK_CLINICAL_TABLES: ClinicalTable[] = [
  { name: 'study', display_name: 'Study Metadata', row_count: 1, columns: [] },
  { name: 'sites', display_name: 'Study Sites', row_count: 5, columns: [] },
  { name: 'dm', display_name: 'Demographics', row_count: 10000, columns: [] },
  { name: 'ae', display_name: 'Adverse Events', row_count: 15324, columns: [] },
  { name: 'ex', display_name: 'Exposure', row_count: 24500, columns: [] },
  { name: 'lb', display_name: 'Laboratory Tests', row_count: 85200, columns: [] },
  { name: 'qs', display_name: 'Questionnaires', row_count: 32000, columns: [] },
  { name: 'vs', display_name: 'Vital Signs', row_count: 91400, columns: [] },
  { name: 'adsl', display_name: 'Subject-Level Analysis', row_count: 10000, columns: [] },
  { name: 'adae', display_name: 'Adverse Event Analysis', row_count: 15324, columns: [] },
  { name: 'adlb', display_name: 'Lab Analysis', row_count: 85200, columns: [] },
  { name: 'advs', display_name: 'Vitals Analysis', row_count: 91400, columns: [] },
  { name: 'adresp', display_name: 'Response Analysis', row_count: 10000, columns: [] },
];

const expandTables = () => fireEvent.click(screen.getByRole('button', { name: 'Expand dataset tables' }));

describe('Dataset Tables Selection & Single Source of Truth', () => {
  it('starts collapsed while keeping all available approved tables selectable', () => {
    render(<SidebarTableSelector availableTables={MOCK_CLINICAL_TABLES} selectedTables={MOCK_CLINICAL_TABLES.map((table) => table.name)} onApplySelection={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Expand dataset tables' }).getAttribute('aria-expanded')).toBe('false');
    expect(screen.getByTestId('selected-count-badge').textContent).toBe('13 selected');
    expect(screen.queryByTestId('checkbox-dm')).toBeNull();
    expandTables();
    expect(screen.getAllByRole('checkbox').filter((checkbox) => (checkbox as HTMLInputElement).checked)).toHaveLength(13);
    expect(getAvailableClinicalTableNames(MOCK_CLINICAL_TABLES)).toHaveLength(13);
  });

  it('1. Selecting 1 table updates checkbox and selected count badge', () => {
    const handleApply = vi.fn();
    render(
      <SidebarTableSelector
        availableTables={MOCK_CLINICAL_TABLES}
        selectedTables={[]}
        onApplySelection={handleApply}
      />
    );
    expandTables();

    const badge = screen.getByTestId('selected-count-badge');
    expect(badge.textContent).toBe('0 selected');

    // Select 1 table: dm
    const dmCheckbox = screen.getByTestId('checkbox-dm') as HTMLInputElement;
    expect(dmCheckbox.checked).toBe(false);

    fireEvent.click(dmCheckbox);

    expect(dmCheckbox.checked).toBe(true);
    expect(badge.textContent).toBe('1 selected');

    // Confirm only 1 box is checked
    const checkedBoxes = screen.getAllByRole('checkbox').filter(
      (cb) => (cb as HTMLInputElement).checked
    );
    expect(checkedBoxes.length).toBe(1);
  });

  it('2. Selecting 3 tables updates checkboxes and selected count badge', () => {
    const handleApply = vi.fn();
    render(
      <SidebarTableSelector
        availableTables={MOCK_CLINICAL_TABLES}
        selectedTables={[]}
        onApplySelection={handleApply}
      />
    );
    expandTables();

    const badge = screen.getByTestId('selected-count-badge');

    // Select 3 tables: study, sites, dm
    fireEvent.click(screen.getByTestId('checkbox-study'));
    fireEvent.click(screen.getByTestId('checkbox-sites'));
    fireEvent.click(screen.getByTestId('checkbox-dm'));

    expect(badge.textContent).toBe('3 selected');

    const checkedBoxes = screen.getAllByRole('checkbox').filter(
      (cb) => (cb as HTMLInputElement).checked
    );
    expect(checkedBoxes.length).toBe(3);
  });

  it('3. Selecting all tables selects all 13 clinical tables and updates count', () => {
    const handleApply = vi.fn();
    render(
      <SidebarTableSelector
        availableTables={MOCK_CLINICAL_TABLES}
        selectedTables={[]}
        onApplySelection={handleApply}
      />
    );
    expandTables();

    const badge = screen.getByTestId('selected-count-badge');
    const selectAllBtn = screen.getByTestId('select-all-btn');

    fireEvent.click(selectAllBtn);

    expect(badge.textContent).toBe('13 selected');

    const checkedBoxes = screen.getAllByRole('checkbox').filter(
      (cb) => (cb as HTMLInputElement).checked
    );
    expect(checkedBoxes.length).toBe(13);
  });

  it('4. Clearing selection resets all checkboxes and count to 0', () => {
    const handleApply = vi.fn();
    render(
      <SidebarTableSelector
        availableTables={MOCK_CLINICAL_TABLES}
        selectedTables={['study', 'sites', 'dm']}
        onApplySelection={handleApply}
      />
    );
    expandTables();

    const badge = screen.getByTestId('selected-count-badge');
    expect(badge.textContent).toBe('3 selected');

    const clearAllBtn = screen.getByTestId('clear-all-btn');
    fireEvent.click(clearAllBtn);

    expect(badge.textContent).toBe('0 selected');

    const checkedBoxes = screen.getAllByRole('checkbox').filter(
      (cb) => (cb as HTMLInputElement).checked
    );
    expect(checkedBoxes.length).toBe(0);
  });

  it('5. Start Analysis sends exactly the selected clinical tables', () => {
    const handleApply = vi.fn();
    render(
      <SidebarTableSelector
        availableTables={MOCK_CLINICAL_TABLES}
        selectedTables={[]}
        onApplySelection={handleApply}
      />
    );
    expandTables();

    // Select 3 tables
    fireEvent.click(screen.getByTestId('checkbox-study'));
    fireEvent.click(screen.getByTestId('checkbox-sites'));
    fireEvent.click(screen.getByTestId('checkbox-dm'));

    const applyBtn = screen.getByTestId('apply-selection-btn');
    fireEvent.click(applyBtn);

    expect(handleApply).toHaveBeenCalledTimes(1);
    expect(handleApply).toHaveBeenCalledWith(['study', 'sites', 'dm']);
  });

  it('excludes a deselected table from the Start Analysis selection', () => {
    const handleApply = vi.fn();
    const allTables = MOCK_CLINICAL_TABLES.map((table) => table.name);
    render(
      <SidebarTableSelector
        availableTables={MOCK_CLINICAL_TABLES}
        selectedTables={allTables}
        onApplySelection={handleApply}
      />
    );
    expandTables();
    fireEvent.click(screen.getByTestId('checkbox-ae'));
    fireEvent.click(screen.getByTestId('apply-selection-btn'));

    expect(handleApply).toHaveBeenCalledWith(allTables.filter((table) => table !== 'ae'));
  });

  it('6. Selected count always strictly equals visibly checked checkboxes', () => {
    const handleApply = vi.fn();
    render(
      <SidebarTableSelector
        availableTables={MOCK_CLINICAL_TABLES}
        selectedTables={[]}
        onApplySelection={handleApply}
      />
    );
    expandTables();

    const badge = screen.getByTestId('selected-count-badge');

    // Helper to verify synchronization
    const verifySync = () => {
      const match = badge.textContent?.match(/^(\d+)\s+selected$/);
      const count = match ? parseInt(match[1], 10) : -1;
      const actualChecked = screen.getAllByRole('checkbox').filter(
        (cb) => (cb as HTMLInputElement).checked
      ).length;
      expect(count).toBe(actualChecked);
    };

    // Initially 0
    verifySync();

    // Select 5 tables: lb, qs, sites, study, vs
    const tablesToClick = ['lb', 'qs', 'sites', 'study', 'vs'];
    for (const t of tablesToClick) {
      fireEvent.click(screen.getByTestId(`checkbox-${t}`));
      verifySync();
    }

    expect(badge.textContent).toBe('5 selected');

    // Add 3 more to make 8 tables
    const extraTables = ['dm', 'ae', 'ex'];
    for (const t of extraTables) {
      fireEvent.click(screen.getByTestId(`checkbox-${t}`));
      verifySync();
    }

    expect(badge.textContent).toBe('8 selected');
  });

  it('7. Tables Data equals applied selection (Single Source of Truth)', () => {
    // Harness component showing synchronized flow between selector and Tables Data section
    const TestSynchronizedDashboard = () => {
      const [appliedTables, setAppliedTables] = useState<string[]>(['study', 'sites', 'dm']);

      return (
        <div>
          <SidebarTableSelector
            availableTables={MOCK_CLINICAL_TABLES}
            selectedTables={appliedTables}
            onApplySelection={(newTables) => setAppliedTables(newTables)}
          />
          <ClinicalMetricsRow selectedTables={appliedTables} />
        </div>
      );
    };

    render(<TestSynchronizedDashboard />);
    expandTables();

    // 1. Initial 3 tables
    const badge = screen.getByTestId('selected-count-badge');
    const tablesDataCard = screen.getByTestId('tables-data');
    expect(badge.textContent).toBe('3 selected');
    expect(tablesDataCard.textContent).toContain('3 Active');
    expect(tablesDataCard.textContent).toContain('study, sites, dm');

    // 2. Select 8 tables and apply
    // study, sites, dm are already checked. Add ae, ex, lb, qs, vs:
    const moreTables = ['ae', 'ex', 'lb', 'qs', 'vs'];
    for (const t of moreTables) {
      fireEvent.click(screen.getByTestId(`checkbox-${t}`));
    }

    expect(badge.textContent).toBe('8 selected');

    // Click Start Analysis
    fireEvent.click(screen.getByTestId('apply-selection-btn'));

    // Tables Data section refreshes and displays exactly those 8 tables!
    expect(badge.textContent).toBe('8 selected');
    expect(tablesDataCard.textContent).toContain('8 Active');
    expect(tablesDataCard.textContent).toContain('study, sites, dm, ae, ex, lb, qs, vs');
  });

  it('8. No legacy EHR table is submitted or accepted from the clinical UI', () => {
    const handleApply = vi.fn();

    // Pass legacy EHR tables in selectedTables prop
    render(
      <SidebarTableSelector
        availableTables={MOCK_CLINICAL_TABLES}
        selectedTables={['patients', 'encounters', 'conditions', 'medications', 'observations', 'procedures']}
        onApplySelection={handleApply}
      />
    );
    expandTables();

    const badge = screen.getByTestId('selected-count-badge');
    // Legacy EHR tables must be completely excluded!
    expect(badge.textContent).toBe('0 selected');

    const checkedBoxes = screen.getAllByRole('checkbox').filter(
      (cb) => (cb as HTMLInputElement).checked
    );
    expect(checkedBoxes.length).toBe(0);

    // Verify filter helper removes all legacy EHR tables
    const sanitized = filterApprovedClinicalTables([
      'patients',
      'encounters',
      'conditions',
      'medications',
      'observations',
      'procedures',
      'study',
      'dm',
    ]);
    expect(sanitized).toEqual(['study', 'dm']);

    for (const legacy of LEGACY_EHR_TABLES) {
      expect(sanitized).not.toContain(legacy);
    }

    // Now select a valid table and apply
    fireEvent.click(screen.getByTestId('checkbox-dm'));
    fireEvent.click(screen.getByTestId('apply-selection-btn'));

    expect(handleApply).toHaveBeenCalledWith(['dm']);
    for (const legacy of LEGACY_EHR_TABLES) {
      expect(handleApply.mock.calls[0][0]).not.toContain(legacy);
    }
  });
});
