import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import { DatasetUploadModal } from '../components/DatasetUploadModal';
import datasetsApi from '../api/datasets';
import { databaseApi } from '../api/database';

vi.mock('../api/datasets', () => ({
  default: {
    previewDataset: vi.fn(),
    uploadDataset: vi.fn(),
    getVersions: vi.fn(),
  },
}));

vi.mock('../api/database', () => ({
  databaseApi: {
    getTables: vi.fn().mockResolvedValue([
      { name: 'dm', display_name: 'Demographics', row_count: 10000, classification: 'CLINICAL' },
      { name: 'ae', display_name: 'Adverse Events', row_count: 15324, classification: 'CLINICAL' },
    ]),
  },
}));

describe('DatasetUploadModal - Duplicate Primary Key Handling & Feedback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('1. Renders upload modal and file picker', () => {
    render(<DatasetUploadModal isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByText('Upload Source Dataset / Schema File')).toBeInTheDocument();
    expect(screen.getByText('Target Database Table')).toBeInTheDocument();
  });

  it('2. Displays duplicate warning card when preview detects duplicate primary keys', async () => {
    (datasetsApi.previewDataset as any).mockResolvedValueOnce({
      status: 'success',
      detected_mode: 'existing',
      proposed_table: 'dm',
      table_already_exists: true,
      total_rows: 5,
      total_columns: 13,
      columns: [
        { name: 'USUBJID', original_name: 'USUBJID', inferred_type: 'VARCHAR(255)', null_count: 0, sample_values: ['STDY001-0001'] },
      ],
      preview_rows: [],
      has_duplicates: true,
      duplicate_count: 2,
      eligible_count: 3,
      primary_key_columns: ['USUBJID'],
      sample_duplicates: [{ USUBJID: 'STDY001-0001' }, { USUBJID: 'STDY001-0002' }],
    });

    render(<DatasetUploadModal isOpen={true} onClose={vi.fn()} />);

    // Upload a dummy CSV file
    const file = new File(['STUDYID,USUBJID\nSTDY001,STDY001-0001\n'], 'DM_sample.csv', { type: 'text/csv' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByTestId('duplicate-warning-card')).toBeInTheDocument();
    });

    expect(screen.getByText('Duplicate Records Detected')).toBeInTheDocument();
    expect(screen.getByText('2 duplicates')).toBeInTheDocument();
    expect(screen.getByText(/3 new records only/i)).toBeInTheDocument();
    expect(screen.getByText(/USUBJID: STDY001-0001/i)).toBeInTheDocument();

    // Verify upload button adjusts text to eligible count
    const uploadBtn = screen.getByTestId('upload-submit-btn');
    expect(uploadBtn).not.toBeDisabled();
    expect(uploadBtn.textContent).toContain('Insert 3 New Records');
  });

  it('3. Disables upload button when all records in file are duplicates (eligible_count === 0)', async () => {
    (datasetsApi.previewDataset as any).mockResolvedValueOnce({
      status: 'success',
      detected_mode: 'existing',
      proposed_table: 'dm',
      table_already_exists: true,
      total_rows: 5,
      total_columns: 13,
      columns: [],
      preview_rows: [],
      has_duplicates: true,
      duplicate_count: 5,
      eligible_count: 0,
      primary_key_columns: ['USUBJID'],
      sample_duplicates: [{ USUBJID: 'STDY001-0001' }],
    });

    render(<DatasetUploadModal isOpen={true} onClose={vi.fn()} />);

    const file = new File(['dummy content'], 'DM_sample.csv', { type: 'text/csv' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByTestId('duplicate-warning-card')).toBeInTheDocument();
    });

    expect(screen.getByText(/All records in this dataset already exist in the database/i)).toBeInTheDocument();

    const uploadBtn = screen.getByTestId('upload-submit-btn');
    expect(uploadBtn).toBeDisabled();
    expect(uploadBtn.textContent).toContain('All Records Already Exist');
  });

  it('4. Submits with duplicate_action="insert_new_only" when user confirms safe insertion', async () => {
    (datasetsApi.previewDataset as any).mockResolvedValueOnce({
      status: 'success',
      detected_mode: 'existing',
      proposed_table: 'dm',
      table_already_exists: true,
      total_rows: 5,
      total_columns: 13,
      columns: [],
      preview_rows: [],
      has_duplicates: true,
      duplicate_count: 2,
      eligible_count: 3,
      primary_key_columns: ['USUBJID'],
      sample_duplicates: [{ USUBJID: 'STDY001-0001' }],
    });

    (datasetsApi.uploadDataset as any).mockResolvedValueOnce({
      status: 'success',
      table_name: 'dm',
      rows_received: 5,
      rows_inserted: 3,
      rows_skipped: 2,
    });

    render(<DatasetUploadModal isOpen={true} onClose={vi.fn()} />);

    const file = new File(['dummy content'], 'DM_sample.csv', { type: 'text/csv' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByTestId('duplicate-warning-card')).toBeInTheDocument();
    });

    const uploadBtn = screen.getByTestId('upload-submit-btn');
    fireEvent.click(uploadBtn);

    await waitFor(() => {
      expect(datasetsApi.uploadDataset).toHaveBeenCalledWith(
        file,
        'dm',
        expect.any(Function),
        false,
        'CLINICAL',
        'APPROVED',
        'insert_new_only'
      );
    });
  });

  it('5. Handles HTTP 409 conflict and updates UI with duplicate conflict guidance', async () => {
    (datasetsApi.previewDataset as any).mockResolvedValueOnce({
      status: 'success',
      detected_mode: 'existing',
      proposed_table: 'dm',
      table_already_exists: true,
      total_rows: 5,
      total_columns: 13,
      columns: [],
      preview_rows: [],
      has_duplicates: false,
    });

    (datasetsApi.uploadDataset as any).mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            status: 'error',
            error_code: 'DUPLICATE_KEY_DETECTED',
            message: 'Duplicate primary key records detected for target table dm.',
            target_table: 'dm',
            duplicate_count: 2,
            eligible_count: 3,
            total_records: 5,
            primary_key_columns: ['USUBJID'],
            sample_duplicates: [{ USUBJID: 'STDY001-0001' }],
          },
        },
      },
    });

    render(<DatasetUploadModal isOpen={true} onClose={vi.fn()} />);

    const file = new File(['dummy content'], 'DM_sample.csv', { type: 'text/csv' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByTestId('upload-submit-btn')).not.toBeDisabled();
    });

    fireEvent.click(screen.getByTestId('upload-submit-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('duplicate-warning-card')).toBeInTheDocument();
    });

    expect(screen.getByText('Duplicate Records Detected')).toBeInTheDocument();
  });
});
