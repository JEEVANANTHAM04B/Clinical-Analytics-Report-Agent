import React, { useState, useRef } from 'react';
import { UploadCloud, FileSpreadsheet, CheckCircle2, AlertCircle, X, Loader2, Database } from 'lucide-react';
import datasetsApi, { UploadDatasetResponse } from '../api/datasets';
import { IngestionResultModal } from './IngestionResultModal';

interface DatasetUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess?: () => void;
  targetTable?: string;
}

export const DatasetUploadModal: React.FC<DatasetUploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
  targetTable: initialTargetTable,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [targetTable, setTargetTable] = useState<string>(initialTargetTable || 'auto');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState<UploadDatasetResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Ingestion Result Popup ────────────────────────────────────────────────
  const [showIngestionResult, setShowIngestionResult] = useState(false);
  const [ingestionError, setIngestionError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setErrorMessage(null);
      setUploadResult(null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setSelectedFile(e.dataTransfer.files[0]);
      setErrorMessage(null);
      setUploadResult(null);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadProgress(0);
    setErrorMessage(null);
    setIngestionError(null);

    try {
      const response = await datasetsApi.uploadDataset(
        selectedFile,
        targetTable === 'auto' ? undefined : targetTable,
        (percent) => {
          setUploadProgress(percent);
        }
      );

      setUploadResult(response);
      // Show the ingestion result popup for success
      setShowIngestionResult(true);
      if (onUploadSuccess) {
        onUploadSuccess();
      }
    } catch (err: any) {
      console.error('Upload failed:', err);
      const detail = err.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : detail?.message || err.message || 'Failed to upload dataset. Please ensure it is a valid CSV or XLSX file.';
      setErrorMessage(msg);
      // Show the ingestion result popup for failure too
      setIngestionError(msg);
      setShowIngestionResult(true);
    } finally {
      setIsUploading(false);
    }
  };

  const handleClose = () => {
    setSelectedFile(null);
    setTargetTable('auto');
    setUploadResult(null);
    setErrorMessage(null);
    setUploadProgress(0);
    setShowIngestionResult(false);
    setIngestionError(null);
    onClose();
  };


  return (
    <>
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl w-full max-w-lg shadow-2xl border border-gray-200 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
              <UploadCloud className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-gray-900 leading-tight">
                Upload Source Dataset / Schema File
              </h3>
              <p className="text-[11px] text-gray-500">
                Upload clinical records (.csv, .xlsx) to validate and load into MySQL
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-1 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Target Table Dropdown */}
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1.5 flex items-center justify-between">
              <span className="flex items-center space-x-1.5">
                <Database className="w-3.5 h-3.5 text-indigo-600" />
                <span>Target Database Table</span>
              </span>
              <span className="text-[10px] text-gray-400 font-normal">
                {targetTable === 'auto' ? 'Auto-detects matching schema' : `Explicitly writing to ${targetTable}`}
              </span>
            </label>
            <select
              value={targetTable}
              onChange={(e) => setTargetTable(e.target.value)}
              disabled={isUploading || !!uploadResult}
              className="w-full text-xs bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-medium"
            >
              <option value="auto">Auto-Detect (Recommended)</option>
              <option value="encounters">encounters</option>
              <option value="patients">patients</option>
              <option value="conditions">conditions</option>
              <option value="medications">medications</option>
              <option value="observations">observations</option>
              <option value="procedures">procedures</option>
            </select>
          </div>

          {/* Dropzone */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-gray-300 hover:border-indigo-500 bg-gray-50/50 hover:bg-indigo-50/20 rounded-xl p-6 text-center cursor-pointer transition-all"
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".csv, .xlsx"
              className="hidden"
            />
            <div className="w-12 h-12 rounded-full bg-indigo-100/60 flex items-center justify-center text-indigo-600 mx-auto mb-3">
              <FileSpreadsheet className="w-6 h-6" />
            </div>
            <p className="text-xs font-semibold text-gray-800">
              {selectedFile ? selectedFile.name : 'Click to browse or drag file here'}
            </p>
            <p className="text-[11px] text-gray-400 mt-1">
              Supports CSV, XLSX up to 50MB
            </p>
            {selectedFile && (
              <span className="inline-block mt-2 px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-mono text-[10px] font-semibold border border-indigo-200">
                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
              </span>
            )}
          </div>

          {/* Progress bar */}
          {isUploading && (
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-medium text-gray-700">
                <span>Processing & loading into MySQL...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-600 transition-all duration-300 rounded-full"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Success summary */}
          {uploadResult && (
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl space-y-2 animate-fadeIn">
              <div className="flex items-center space-x-2 text-emerald-800 text-xs font-bold">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>
                  {uploadResult.table_name
                    ? `Loaded into MySQL Table '${uploadResult.table_name}' Successfully!`
                    : 'Dataset Ingested & Validated Successfully!'}
                </span>
              </div>
              <div className="grid grid-cols-4 gap-2 pt-2 border-t border-emerald-200/60 text-[11px] font-mono">
                <div className="bg-white/80 p-2 rounded border border-emerald-100">
                  <span className="text-gray-500 block text-[9px] uppercase">Table</span>
                  <span className="font-bold text-gray-800 truncate block">
                    {uploadResult.table_name || 'Auto'}
                  </span>
                </div>
                <div className="bg-white/80 p-2 rounded border border-emerald-100">
                  <span className="text-gray-500 block text-[9px] uppercase">Received</span>
                  <span className="font-bold text-gray-800">
                    {(uploadResult.rows_received ?? uploadResult.dataset?.row_count ?? 0).toLocaleString()}
                  </span>
                </div>
                <div className="bg-white/80 p-2 rounded border border-emerald-100">
                  <span className="text-gray-500 block text-[9px] uppercase">Inserted</span>
                  <span className="font-bold text-emerald-700">
                    {(uploadResult.rows_inserted ?? uploadResult.rows_loaded ?? 0).toLocaleString()}
                  </span>
                </div>
                <div className="bg-white/80 p-2 rounded border border-emerald-100">
                  <span className="text-gray-500 block text-[9px] uppercase">Skipped</span>
                  <span className="font-bold text-amber-700">
                    {(uploadResult.rows_skipped ?? 0).toLocaleString()}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Error Message */}
          {errorMessage && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-start space-x-2 animate-fadeIn">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span className="leading-relaxed">{errorMessage}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex items-center justify-end space-x-2">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            {uploadResult ? 'Done' : 'Cancel'}
          </button>
          {!uploadResult && (
            <button
              onClick={handleUpload}
              disabled={!selectedFile || isUploading}
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-lg shadow-sm flex items-center space-x-1.5 transition-all cursor-pointer"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Ingesting...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="w-3.5 h-3.5" />
                  <span>Upload Dataset</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>

    {/* Ingestion Result Popup — rendered at z-60, above the upload modal */}
    <IngestionResultModal
      isOpen={showIngestionResult}
      onClose={() => setShowIngestionResult(false)}
      response={uploadResult}
      errorMessage={ingestionError}
    />
  </>
  );
};

export default DatasetUploadModal;
