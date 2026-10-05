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

export const datasetsApi = {
  uploadDataset: async (
    file: File,
    targetTable?: string,
    onProgress?: (percent: number) => void
  ): Promise<UploadDatasetResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (targetTable && targetTable !== 'auto' && targetTable.trim() !== '') {
      formData.append('target_table', targetTable.trim());
    }
    formData.append('if_exists', 'append');

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
