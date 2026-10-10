import React, { useState, useRef, useEffect } from 'react';
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  X,
  Loader2,
  Database,
  Table2,
  Sparkles,
  Layers
} from 'lucide-react';
import datasetsApi, { UploadDatasetResponse, PreviewDatasetResponse } from '../api/datasets';
import { databaseApi } from '../api/database';
import { ClinicalTable } from '../types/analytics';
import { IngestionResultModal } from './IngestionResultModal';

interface DatasetUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess?: () => void;
  targetTable?: string;
  availableTables?: ClinicalTable[];
}

export const DatasetUploadModal: React.FC<DatasetUploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
  targetTable: initialTargetTable,
  availableTables: propTables,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [targetTable, setTargetTable] = useState<string>(initialTargetTable || 'auto');
  const [newTableName, setNewTableName] = useState<string>('');
  const [registeredTables, setRegisteredTables] = useState<ClinicalTable[]>(propTables || []);
  const [isPreviewing, setIsPreviewing] = useState<boolean>(false);
  const [previewData, setPreviewData] = useState<PreviewDatasetResponse | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadResult, setUploadResult] = useState<UploadDatasetResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [approveForClinical, setApproveForClinical] = useState<boolean>(true);
  const [insertNewOnly, setInsertNewOnly] = useState<boolean>(true);
  const [duplicateConflict, setDuplicateConflict] = useState<{
    targetTable: string;
    pkColumns: string[];
    totalRecords: number;
    duplicateCount: number;
    eligibleCount: number;
    sampleDuplicates: Record<string, any>[];
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Ingestion Result Popup ────────────────────────────────────────────────
  const [showIngestionResult, setShowIngestionResult] = useState(false);
  const [ingestionError, setIngestionError] = useState<string | null>(null);

  // Refresh registered tables from MySQL when modal opens
  useEffect(() => {
    if (isOpen) {
      databaseApi.getTables()
        .then((res) => {
          if (Array.isArray(res) && res.length > 0) {
            setRegisteredTables(res);
          }
        })
        .catch((err) => {
          console.error('Failed to load registered database tables:', err);
        });
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const sanitizeName = (raw: string): string => {
    return raw
      .replace(/\.[^/.]+$/, '')
      .toLowerCase()
      .replace(/[^a-z0-9_]/g, '_')
      .replace(/_+/g, '_')
      .replace(/^_+|_+$/g, '');
  };

  const runPreview = async (file: File, mode: string, tableParam?: string) => {
    setIsPreviewing(true);
    try {
      const modeParam = mode === '__new__' ? 'new' : mode === 'auto' ? 'auto' : 'existing';
      const response = await datasetsApi.previewDataset(file, modeParam, tableParam);
      setPreviewData(response);

      if (mode === 'auto' && response.detected_mode === 'new' && response.proposed_table) {
        if (!newTableName) {
          setNewTableName(response.proposed_table);
        }
      }
    } catch (err: any) {
      console.warn('Dataset preview request failed:', err);
      // Keep going without blocking user upload
      setPreviewData(null);
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setErrorMessage(null);
      setUploadResult(null);
      setDuplicateConflict(null);
      setInsertNewOnly(true);
      setPreviewData(null);

      const defaultName = sanitizeName(file.name);
      if (!newTableName || targetTable === '__new__') {
        setNewTableName(defaultName);
      }

      runPreview(file, targetTable, targetTable === '__new__' ? (newTableName || defaultName) : targetTable);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
      setErrorMessage(null);
      setUploadResult(null);
      setDuplicateConflict(null);
      setInsertNewOnly(true);
      setPreviewData(null);

      const defaultName = sanitizeName(file.name);
      if (!newTableName || targetTable === '__new__') {
        setNewTableName(defaultName);
      }

      runPreview(file, targetTable, targetTable === '__new__' ? (newTableName || defaultName) : targetTable);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleTargetTableChange = (val: string) => {
    setTargetTable(val);
    setErrorMessage(null);
    setDuplicateConflict(null);
    setInsertNewOnly(true);

    if (selectedFile) {
      const defaultName = sanitizeName(selectedFile.name);
      const targetParam = val === '__new__' ? (newTableName || defaultName) : val;
      runPreview(selectedFile, val, targetParam);
    }
  };

  const handleNewTableNameChange = (val: string) => {
    setNewTableName(val);
    setErrorMessage(null);

    const clean = sanitizeName(val);
    const exists = registeredTables.some((t) => t.name.toLowerCase() === clean.toLowerCase());

    if (previewData) {
      setPreviewData({
        ...previewData,
        proposed_table: clean,
        table_already_exists: exists,
        warning: exists
          ? `Table ${clean} already exists. Choose another name or explicitly select an existing table as the upload target.`
          : undefined,
      });
    }
  };

  // Determine if there is a duplicate table conflict
  const isCreatingNew = targetTable === '__new__' || (targetTable === 'auto' && previewData?.detected_mode === 'new');
  const effectiveProposedName = targetTable === '__new__'
    ? (newTableName.trim() || (selectedFile ? sanitizeName(selectedFile.name) : ''))
    : (previewData?.proposed_table || (selectedFile ? sanitizeName(selectedFile.name) : ''));

  const tableAlreadyExists = isCreatingNew && (
    previewData?.table_already_exists ||
    registeredTables.some((t) => t.name.toLowerCase() === effectiveProposedName.toLowerCase())
  );

  const handleUpload = async () => {
    if (!selectedFile) return;

    if (targetTable === '__new__' && !newTableName.trim()) {
      setErrorMessage('Please enter a valid table name.');
      return;
    }

    if (tableAlreadyExists) {
      setErrorMessage(
        `Table ${effectiveProposedName} already exists. Choose another name or explicitly select an existing table as the upload target.`
      );
      return;
    }

    const isDuplicateCase = previewData?.has_duplicates || !!duplicateConflict;
    const effectiveEligible = previewData?.eligible_count ?? duplicateConflict?.eligibleCount ?? 0;

    if (isDuplicateCase && effectiveEligible === 0) {
      setErrorMessage(
        'All records in this dataset already exist in target table. No new records can be inserted.'
      );
      return;
    }

    if (isDuplicateCase && !insertNewOnly) {
      setErrorMessage(
        'Duplicate records detected. Please select "Insert New Records Only" to proceed safely.'
      );
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);
    setErrorMessage(null);
    setIngestionError(null);

    const isNew = targetTable === '__new__' || (targetTable === 'auto' && previewData?.detected_mode === 'new');
    let finalTarget: string | undefined = undefined;

    if (targetTable === '__new__') {
      finalTarget = newTableName.trim();
    } else if (targetTable === 'auto') {
      finalTarget = isNew ? (newTableName.trim() || previewData?.proposed_table) : previewData?.proposed_table;
    } else {
      finalTarget = targetTable;
    }

    const dupAction = isDuplicateCase && insertNewOnly ? 'insert_new_only' : undefined;

    try {
      const response = await datasetsApi.uploadDataset(
        selectedFile,
        finalTarget,
        (percent) => {
          setUploadProgress(percent);
        },
        isNew,
        'CLINICAL',
        approveForClinical ? 'APPROVED' : 'PENDING',
        dupAction
      );

      setUploadResult(response);
      setShowIngestionResult(true);

      // Notify application of new/updated tables so sidebars and selectors refresh
      window.dispatchEvent(new CustomEvent('clinical-tables-updated'));
      if (onUploadSuccess) {
        onUploadSuccess();
      }
    } catch (err: any) {
      console.error('Upload failed:', err);
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409 || detail?.error_code === 'DUPLICATE_KEY_DETECTED') {
        const dupInfo = {
          targetTable: detail?.target_table || finalTarget || 'target table',
          pkColumns: detail?.primary_key_columns || ['PRIMARY KEY'],
          totalRecords: detail?.total_records || 0,
          duplicateCount: detail?.duplicate_count || 0,
          eligibleCount: detail?.eligible_count || 0,
          sampleDuplicates: detail?.sample_duplicates || [],
        };
        setDuplicateConflict(dupInfo);
        const userMsg = detail?.message || 'Duplicate primary key records detected in target table.';
        setErrorMessage(userMsg);
        setIngestionError(userMsg);
        return;
      }
      const msg =
        typeof detail === 'string'
          ? detail
          : detail?.message || err.message || 'Failed to upload dataset. Please ensure it is a valid CSV or XLSX file.';
      setErrorMessage(msg);
      setIngestionError(msg);
      setShowIngestionResult(true);
    } finally {
      setIsUploading(false);
    }
  };

  const handleClose = () => {
    setSelectedFile(null);
    setTargetTable('auto');
    setNewTableName('');
    setPreviewData(null);
    setUploadResult(null);
    setErrorMessage(null);
    setUploadProgress(0);
    setShowIngestionResult(false);
    setIngestionError(null);
    setInsertNewOnly(true);
    setDuplicateConflict(null);
    onClose();
  };

  return (
    <>
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl w-full max-w-lg shadow-2xl border border-gray-200 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between flex-shrink-0">
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
        <div className="p-6 space-y-4 overflow-y-auto flex-1">
          {/* Target Table Dropdown */}
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1.5 flex items-center justify-between">
              <span className="flex items-center space-x-1.5">
                <Database className="w-3.5 h-3.5 text-indigo-600" />
                <span>Target Database Table</span>
              </span>
              <span className="text-[10px] text-gray-400 font-normal">
                {targetTable === 'auto'
                  ? 'Auto-detects matching schema'
                  : targetTable === '__new__'
                  ? 'Creates a new MySQL table'
                  : `Writing to ${targetTable}`}
              </span>
            </label>
            <select
              value={targetTable}
              onChange={(e) => handleTargetTableChange(e.target.value)}
              disabled={isUploading || !!uploadResult}
              className="w-full text-xs bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-medium cursor-pointer"
            >
              <option value="auto">Auto-Detect (Recommended)</option>
              <option value="__new__">Create New Table</option>
              {registeredTables.filter((t) => !t.classification || t.classification === 'CLINICAL').length > 0 && (
                <optgroup label="Registered Database Tables">
                  {registeredTables
                    .filter((t) => !t.classification || t.classification === 'CLINICAL')
                    .map((tbl) => (
                    <option key={tbl.name} value={tbl.name}>
                      {tbl.name} ({tbl.row_count > 999 ? `${(tbl.row_count / 1000).toFixed(0)}k` : tbl.row_count} rows)
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
          </div>

          {/* New Table Name Input when Create New Table is selected */}
          {targetTable === '__new__' && (
            <div className="animate-fadeIn">
              <label className="block text-xs font-semibold text-gray-700 mb-1.5 flex items-center justify-between">
                <span className="flex items-center space-x-1.5">
                  <Table2 className="w-3.5 h-3.5 text-indigo-600" />
                  <span>New Table Name</span>
                </span>
                <span className="text-[10px] text-gray-400 font-normal">
                  Example: custom_study_cohort
                </span>
              </label>
              <input
                type="text"
                value={newTableName}
                onChange={(e) => handleNewTableNameChange(e.target.value)}
                placeholder="custom_study_cohort"
                disabled={isUploading || !!uploadResult}
                className="w-full text-xs bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-mono font-medium"
              />
              <div className="mt-2.5 flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="approve-clinical-cb"
                  checked={approveForClinical}
                  onChange={(e) => setApproveForClinical(e.target.checked)}
                  disabled={isUploading || !!uploadResult}
                  className="w-3.5 h-3.5 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500 cursor-pointer"
                />
                <label htmlFor="approve-clinical-cb" className="text-xs text-gray-700 font-medium cursor-pointer select-none">
                  Register & approve table for Clinical Analytics
                </label>
              </div>
            </div>
          )}

          {/* Dropzone */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-gray-300 hover:border-indigo-500 bg-gray-50/50 hover:bg-indigo-50/20 rounded-xl p-5 text-center cursor-pointer transition-all"
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".csv, .xlsx"
              className="hidden"
            />
            <div className="w-10 h-10 rounded-full bg-indigo-100/60 flex items-center justify-center text-indigo-600 mx-auto mb-2">
              <FileSpreadsheet className="w-5 h-5" />
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

          {/* Schema & Dataset Preview Section */}
          {isPreviewing && (
            <div className="p-3 bg-gray-50 rounded-xl border border-gray-200 flex items-center justify-center space-x-2 text-xs text-gray-600">
              <Loader2 className="w-4 h-4 text-indigo-600 animate-spin" />
              <span>Inspecting columns and inferring MySQL data types...</span>
            </div>
          )}

          {previewData && !isPreviewing && !uploadResult && (
            <div className="p-3.5 bg-gray-50/80 rounded-xl border border-gray-200 space-y-2.5 text-xs animate-fadeIn">
              {/* Preview Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-1.5">
                  <span className="text-[11px] font-semibold text-gray-700">
                    {targetTable === '__new__' || (targetTable === 'auto' && previewData.detected_mode === 'new')
                      ? 'Proposed New Table:'
                      : 'Target Table:'}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-indigo-50 border border-indigo-200 text-indigo-700 font-mono text-[10px] font-bold">
                    {targetTable === '__new__' ? (newTableName || previewData.proposed_table) : previewData.proposed_table}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-gray-500 bg-white px-2 py-0.5 rounded border border-gray-200">
                  {previewData.total_rows.toLocaleString()} rows × {previewData.total_columns} cols
                </span>
              </div>

              {/* Table Conflict Warning */}
              {tableAlreadyExists && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-[11px] flex items-start space-x-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-rose-600" />
                  <span className="leading-tight font-medium">
                    Table {effectiveProposedName} already exists. Choose another name or explicitly select an existing table as the upload target.
                  </span>
                </div>
              )}

              {/* Duplicate Primary Key Warning & Action Card */}
              {(previewData?.has_duplicates || !!duplicateConflict) && (
                <div data-testid="duplicate-warning-card" className="p-3 bg-amber-50 border border-amber-200 rounded-xl space-y-2 text-xs animate-fadeIn">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-1.5 font-bold text-amber-900">
                      <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                      <span>Duplicate Records Detected</span>
                    </div>
                    <span className="px-2 py-0.5 rounded-full bg-amber-100 border border-amber-300 text-amber-800 font-mono text-[10px] font-bold">
                      {(previewData?.duplicate_count ?? duplicateConflict?.duplicateCount ?? 0).toLocaleString()} duplicates
                    </span>
                  </div>

                  <p className="text-[11px] text-amber-800 leading-relaxed">
                    Target table <strong className="font-mono text-gray-900">{previewData?.proposed_table || duplicateConflict?.targetTable}</strong> already contains records with matching primary key values
                    {(previewData?.primary_key_columns || duplicateConflict?.pkColumns)?.length ? (
                      <> (<code className="font-mono font-semibold">{(previewData?.primary_key_columns || duplicateConflict?.pkColumns)?.join(', ')}</code>)</>
                    ) : null}. Existing clinical records will not be overwritten.
                  </p>

                  {/* Duplicate stats breakdown */}
                  <div className="grid grid-cols-3 gap-2 py-1 text-center font-mono text-[10px]">
                    <div className="bg-white/90 p-1.5 rounded border border-amber-200">
                      <span className="text-gray-500 block text-[9px] uppercase">Uploaded</span>
                      <span className="font-bold text-gray-800">
                        {(previewData?.total_rows ?? duplicateConflict?.totalRecords ?? 0).toLocaleString()}
                      </span>
                    </div>
                    <div className="bg-white/90 p-1.5 rounded border border-amber-200">
                      <span className="text-amber-600 block text-[9px] uppercase">Duplicates</span>
                      <span className="font-bold text-amber-700">
                        {(previewData?.duplicate_count ?? duplicateConflict?.duplicateCount ?? 0).toLocaleString()}
                      </span>
                    </div>
                    <div className="bg-white/90 p-1.5 rounded border border-amber-200">
                      <span className="text-emerald-600 block text-[9px] uppercase">Eligible</span>
                      <span className="font-bold text-emerald-700">
                        {(previewData?.eligible_count ?? duplicateConflict?.eligibleCount ?? 0).toLocaleString()}
                      </span>
                    </div>
                  </div>

                  {/* Sample duplicate values */}
                  {((previewData?.sample_duplicates && previewData.sample_duplicates.length > 0) ||
                    (duplicateConflict?.sampleDuplicates && duplicateConflict.sampleDuplicates.length > 0)) && (
                    <div className="pt-0.5">
                      <span className="text-[10px] text-amber-700 font-semibold block mb-1">
                        Sample conflicting keys:
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {(previewData?.sample_duplicates || duplicateConflict?.sampleDuplicates || []).map((sample, idx) => (
                          <span
                            key={idx}
                            className="bg-white px-2 py-0.5 rounded border border-amber-200 font-mono text-[10px] text-amber-900 font-medium"
                          >
                            {Object.entries(sample)
                              .map(([k, v]) => `${k}: ${v}`)
                              .join(', ')}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Explicit user action selector */}
                  {(previewData?.eligible_count ?? duplicateConflict?.eligibleCount ?? 0) > 0 ? (
                    <div className="pt-2 border-t border-amber-200/80">
                      <label className="flex items-start space-x-2 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          data-testid="insert-new-only-checkbox"
                          checked={insertNewOnly}
                          onChange={(e) => setInsertNewOnly(e.target.checked)}
                          disabled={isUploading || !!uploadResult}
                          className="w-3.5 h-3.5 mt-0.5 text-indigo-600 rounded border-amber-300 focus:ring-indigo-500 cursor-pointer"
                        />
                        <div className="text-[11px] text-amber-900">
                          <span className="font-semibold block">
                            Insert {(previewData?.eligible_count ?? duplicateConflict?.eligibleCount ?? 0).toLocaleString()} new records only (skip duplicates)
                          </span>
                          <span className="text-[10px] text-amber-700">
                            Preserves existing clinical records unchanged and skips duplicate rows safely.
                          </span>
                        </div>
                      </label>
                    </div>
                  ) : (
                    <div className="pt-1.5 border-t border-amber-200/80 text-[11px] text-amber-900 font-semibold">
                      All records in this dataset already exist in the database. No new records can be inserted.
                    </div>
                  )}
                </div>
              )}

              {/* Auto-detect info message */}
              {targetTable === 'auto' && previewData.match_message && !tableAlreadyExists && (
                <div className="p-2 bg-indigo-50/80 border border-indigo-100 rounded-lg text-indigo-800 text-[10px] flex items-center space-x-1.5 font-medium">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-600 flex-shrink-0" />
                  <span>{previewData.match_message}</span>
                </div>
              )}

              {/* Inferred Schema Table */}
              <div className="max-h-32 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-2xs">
                <table className="w-full text-left border-collapse text-[10px]">
                  <thead className="bg-gray-100/80 sticky top-0 border-b border-gray-200 text-gray-600">
                    <tr>
                      <th className="py-1 px-2.5 font-semibold">Column</th>
                      <th className="py-1 px-2.5 font-semibold">Inferred Type</th>
                      <th className="py-1 px-2.5 font-semibold">Nulls</th>
                      <th className="py-1 px-2.5 font-semibold">Sample Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 font-mono">
                    {previewData.columns.map((col) => (
                      <tr key={col.name} className="hover:bg-gray-50/70">
                        <td className="py-1 px-2.5 font-semibold text-gray-800">{col.name}</td>
                        <td className="py-1 px-2.5">
                          <span className="px-1.5 py-0.2 rounded bg-indigo-50 text-indigo-700 border border-indigo-100 text-[9px] font-bold">
                            {col.inferred_type}
                          </span>
                        </td>
                        <td className="py-1 px-2.5 text-gray-400">
                          {col.null_count > 0 ? `${col.null_count}` : '0'}
                        </td>
                        <td className="py-1 px-2.5 text-gray-600 truncate max-w-[130px]">
                          {col.sample_values?.length > 0 ? col.sample_values.join(', ') : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

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
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex items-center justify-end space-x-2 flex-shrink-0">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 rounded-lg transition-colors cursor-pointer"
          >
            {uploadResult ? 'Done' : 'Cancel'}
          </button>
          {!uploadResult && (
            <button
              onClick={handleUpload}
              data-testid="upload-submit-btn"
              disabled={
                !selectedFile ||
                isUploading ||
                isPreviewing ||
                tableAlreadyExists ||
                (targetTable === '__new__' && !newTableName.trim()) ||
                ((previewData?.has_duplicates || !!duplicateConflict) &&
                  ((previewData?.eligible_count ?? duplicateConflict?.eligibleCount ?? 0) === 0 || !insertNewOnly))
              }
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-lg shadow-sm flex items-center space-x-1.5 transition-all cursor-pointer"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Ingesting...</span>
                </>
              ) : (previewData?.has_duplicates || !!duplicateConflict) ? (
                (previewData?.eligible_count ?? duplicateConflict?.eligibleCount ?? 0) === 0 ? (
                  <span>All Records Already Exist</span>
                ) : (
                  <>
                    <UploadCloud className="w-3.5 h-3.5" />
                    <span>
                      Insert {(previewData?.eligible_count ?? duplicateConflict?.eligibleCount ?? 0).toLocaleString()} New Records
                    </span>
                  </>
                )
              ) : (
                <>
                  <UploadCloud className="w-3.5 h-3.5" />
                  <span>
                    {targetTable === '__new__' || (targetTable === 'auto' && previewData?.detected_mode === 'new')
                      ? 'Confirm & Create Table'
                      : 'Upload Dataset'}
                  </span>
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
