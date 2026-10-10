import apiClient from './client';

export interface DatasetVersionItem {
  id: number;
  dataset_name: string;
  source_filename: string;
  source_file_type: string;
  version_number: number;
  row_count: number;
  column_count: number;
  status: string;
  loaded_at: string;
}

export interface ListVersionsResponse {
  status: string;
  count: number;
  versions: DatasetVersionItem[];
}

export interface UploadDatasetResponse {
  status: string;
  message?: string;
  table_name?: string;
  rows_loaded?: number;
  rows_received?: number;
  rows_inserted?: number;
  rows_skipped?: number;
  rows_failed?: number;
  columns?: number;
  dataset?: {
    original_filename?: string;
    saved_filename?: string;
    file_name?: string;
    file_type: string;
    file_size_mb?: number;
    row_count: number;
    column_count: number;
    columns: Array<{
      name: string;
      dtype: string;
      null_count: number;
      null_percentage: number;
      unique_count: number;
    }>;
  };
  quality?: {
    total_rows: number;
    total_columns: number;
    duplicate_rows?: number;
    duplicate_row_count?: number;
    duplicate_percentage?: number;
    missing_cells_percentage?: number;
    quality_flags?: string[];
  };
}

export interface InferredColumnPreview {
  name: string;
  original_name: string;
  inferred_type: string;
  null_count: number;
  sample_values: string[];
}

export interface PreviewDatasetResponse {
  status: string;
  detected_mode: 'new' | 'existing' | 'ambiguous';
  proposed_table: string;
  table_already_exists: boolean;
  match_confidence?: number;
  match_message?: string;
  warning?: string;
  total_rows: number;
  total_columns: number;
  columns: InferredColumnPreview[];
  preview_rows: Record<string, any>[];
}

export const datasetsApi = {
  previewDataset: async (
    file: File,
    targetMode: string = 'auto',
    targetTable?: string
  ): Promise<PreviewDatasetResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('target_mode', targetMode);
    if (targetTable && targetTable.trim() !== '') {
      formData.append('target_table', targetTable.trim());
    }

    const res = await apiClient.post<PreviewDatasetResponse>('/ingestion/preview', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return res.data;
  },

  uploadDataset: async (
    file: File,
    targetTable?: string,
    onProgress?: (percent: number) => void,
    isNewTable: boolean = false,
    classification: string = 'CLINICAL',
    approvalStatus: string = 'APPROVED'
  ): Promise<UploadDatasetResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (targetTable && targetTable !== 'auto' && targetTable.trim() !== '') {
      formData.append('target_table', targetTable.trim());
    }
    formData.append('if_exists', isNewTable ? 'fail' : 'append');
    formData.append('is_new_table', String(isNewTable));
    formData.append('classification', classification);
    formData.append('approval_status', approvalStatus);

    const res = await apiClient.post<UploadDatasetResponse>('/ingestion/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });

    return res.data;
  },

  getVersions: async (): Promise<ListVersionsResponse> => {
    const res = await apiClient.get<ListVersionsResponse>('/database/versions');
    return res.data;
  },
};

export default datasetsApi;
