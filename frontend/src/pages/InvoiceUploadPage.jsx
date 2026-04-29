/**
 * Japan OCR Tool - Invoice Upload Page
 *
 * Primary page for submitting PDF invoices to the OCR processing pipeline.
 * Supports both single-file and bulk (multi-file) upload modes with real-time
 * job progress polling and extracted field display.
 *
 * Key Features:
 * - Single Upload: Drag-and-drop or file-picker for one invoice at a time
 * - Bulk Upload: Multi-file selection with per-file progress and status table
 * - Job Polling: Polls bulk job status until all items reach a terminal state
 * - Result Persistence: Caches last single-upload result in localStorage
 *
 * Dependencies: services/api, i18n, ImportantNotice component
 * Author: SHIRIN MIRZI M K
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ImportantNotice from '../components/ImportantNotice';
import { uploadInvoice, bulkUploadInvoices, getBulkJob } from '../services/api';
import { t } from '../i18n';
import { useLang } from '../context/LangContext';

// ── Invoice type toggle ────────────────────────────────────────────────────────

function InvoiceTypeToggle({ value, onChange }) {
  useLang();
  return (
    <div className="mb-4">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">{t('invoice_type')}</p>
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 max-w-xs" role="radiogroup" aria-label={t('invoice_type')}>
        <button
          role="radio"
          aria-checked={value === 'monthly'}
          onClick={() => onChange('monthly')}
          className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${
            value === 'monthly'
              ? 'bg-white text-gray-900 shadow'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          {t('invoice_type_monthly')}
        </button>
        <button
          role="radio"
          aria-checked={value === 'daily'}
          onClick={() => onChange('daily')}
          className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${
            value === 'daily'
              ? 'bg-white text-gray-900 shadow'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          {t('invoice_type_daily')}
        </button>
      </div>
    </div>
  );
}

// ── Single upload ──────────────────────────────────────────────────────────────

const DAILY_FIELD_LABELS = [
  ['customer_code', 'customer_code'],
  ['invoice_number', 'invoice_number'],
  ['invoice_date', 'invoice_date'],
];

const MONTHLY_FIELD_LABELS = [
  ['invoice_number', 'invoice_number'],
  ['vendor_name', 'vendor_name'],
  ['vendor_address', 'vendor_address'],
  ['customer_name', 'customer_name'],
  ['customer_address', 'customer_address'],
  ['invoice_date', 'invoice_date'],
  ['due_date', 'due_date'],
  ['total_amount', 'total_amount'],
  ['tax_amount', 'tax_amount'],
  ['subtotal', 'subtotal'],
  ['currency', 'currency'],
];

function SingleUpload() {
  const [file, setFile] = useState(null);
  const [fileName, setFileName] = useState(() => localStorage.getItem('single_file_name') || null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(() => {
    try {
      const stored = localStorage.getItem('single_upload_result');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [error, setError] = useState(null);
  const [invoiceType, setInvoiceType] = useState(() => localStorage.getItem('single_invoice_type') || 'daily');
  const inputRef = useRef();

  const handleFile = (f) => {
    if (f && f.name.toLowerCase().endsWith('.pdf')) {
      setFile(f);
      setFileName(f.name);
      localStorage.setItem('single_file_name', f.name);
      setError(null);
      setResult(null);
      localStorage.removeItem('single_upload_result');
    } else {
      setError('Only PDF files are supported.');
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    handleFile(f);
  };

  const handleProcess = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const data = await uploadInvoice(file, invoiceType);
      setResult(data);
      localStorage.setItem('single_upload_result', JSON.stringify(data));
      localStorage.setItem('single_invoice_type', invoiceType);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Processing failed');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setFileName(null);
    setResult(null);
    setError(null);
    localStorage.removeItem('single_upload_result');
    localStorage.removeItem('single_file_name');
    localStorage.removeItem('single_invoice_type');
  };

  const fieldLabels = invoiceType === 'daily' ? DAILY_FIELD_LABELS : MONTHLY_FIELD_LABELS;

  return (
    <div>
      {!result ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 w-full">
          <InvoiceTypeToggle value={invoiceType} onChange={setInvoiceType} />

          <div
            className={`border-2 border-dashed rounded-xl p-8 sm:p-12 text-center cursor-pointer transition-colors ${
              dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <div className="text-4xl mb-3">📄</div>
            <p className="text-gray-500 text-sm">{t('upload_hint')}</p>
            {file ? (
              <p className="mt-2 text-sm font-medium text-blue-600">{file.name}</p>
            ) : fileName ? (
              <p className="mt-2 text-xs text-gray-400">{fileName} — select again to reprocess</p>
            ) : null}
            <input
              ref={inputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => handleFile(e.target.files[0])}
            />
          </div>

          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
              <span className="text-red-400 mt-0.5">⚠</span>
              {error}
            </div>
          )}

          <div className="mt-5 flex gap-3">
            <button
              onClick={() => inputRef.current?.click()}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            >
              {t('upload_choose')}
            </button>
            <button
              onClick={handleProcess}
              disabled={!file || loading}
              className="px-6 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-50 transition-opacity hover:opacity-90"
              style={{ backgroundColor: '#009DD0' }}
            >
              {loading ? t('upload_processing') : t('upload_process')}
            </button>
          </div>
        </div>
      ) : (
        <div className="w-full">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Invoice Data Extracted</h2>
              <span className={`px-2.5 py-1 text-xs rounded-full font-medium ${result.output_folder === 'Error' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}`}>
                {result.output_folder === 'Error' ? '✗ Error' : '✓ Processed'}
              </span>
            </div>

            {invoiceType === 'daily' && (
              <div className="mb-5 p-4 bg-gray-50 rounded-lg space-y-2 border border-gray-100">
                {result.renamed_filename && (
                  <p className="text-sm">
                    <span className="font-medium">✅ Renamed filename:</span>{' '}
                    <span className="font-mono text-blue-700">{result.renamed_filename}</span>
                  </p>
                )}
                <p className="text-sm">
                  <span className="font-medium">📁 Output folder:</span>{' '}
                  <span className={`font-medium ${result.output_folder === 'Error' ? 'text-red-600' : 'text-green-600'}`}>
                    {result.output_folder}
                  </span>
                </p>
                {result.execution_folder && (
                  <p className="text-sm">
                    <span className="font-medium">🗂️ Execution folder:</span>{' '}
                    <span className="font-mono text-gray-700">{result.execution_folder}</span>
                  </p>
                )}
                {result.blob_path && (
                  <p className="text-sm text-gray-500 break-all">
                    <span className="font-medium">Blob path:</span> {result.blob_path}
                  </p>
                )}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              {fieldLabels.map(([key, label]) => (
                <div key={key} className={key.includes('address') ? 'col-span-2' : ''}>
                  <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">{t(label)}</p>
                  <p className="text-sm font-medium text-gray-900">{result[key] || '—'}</p>
                </div>
              ))}
            </div>
          </div>

          {result.line_items && result.line_items.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-4">
              <h3 className="font-semibold text-gray-900 mb-3">{t('line_items')}</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left border-b border-gray-200">
                    <th className="pb-2 font-medium text-gray-500 text-xs uppercase">Description</th>
                    <th className="pb-2 font-medium text-gray-500 text-xs uppercase">Qty</th>
                    <th className="pb-2 font-medium text-gray-500 text-xs uppercase">Unit Price</th>
                    <th className="pb-2 font-medium text-gray-500 text-xs uppercase">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {result.line_items.map((item, i) => (
                    <tr key={i} className="border-b border-gray-100 last:border-0">
                      <td className="py-2 text-gray-900">{item.description}</td>
                      <td className="py-2 text-gray-700">{item.quantity}</td>
                      <td className="py-2 text-gray-700">{item.unit_price}</td>
                      <td className="py-2 text-gray-700">{item.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <button
            onClick={handleReset}
            className="px-6 py-2 rounded-lg text-white text-sm font-medium transition-opacity hover:opacity-90"
            style={{ backgroundColor: '#002F45' }}
          >
            Upload Another
          </button>
        </div>
      )}
    </div>
  );
}

// ── Bulk upload ────────────────────────────────────────────────────────────────

const TERMINAL_STATUSES = new Set(['done', 'failed', 'cancelled', 'partial']);
const POLL_INTERVAL = 1200;

const statusBadge = (status) => {
  const map = {
    done: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    cancelled: 'bg-gray-100 text-gray-500',
    processing: 'bg-indigo-100 text-indigo-700',
    queued: 'bg-yellow-50 text-yellow-700 border border-yellow-200',
    partial: 'bg-orange-100 text-orange-800',
    pending: 'bg-yellow-50 text-yellow-700 border border-yellow-200',
  };
  return map[status] || 'bg-gray-100 text-gray-500';
};

function buildRowsFromJob(job) {
  if (!job) return [];
  const results = job.results || {};
  const isRunning = !TERMINAL_STATUSES.has(job.status);
  const processedCount = job.processed_count ?? 0;
  return (job.filenames || []).map((filename, index) => {
    const r = results[filename];
    let status;
    if (r) {
      status = r.status;
    } else if (isRunning) {
      // Partial results are written after each file completes.  Files
      // without a result entry yet are either currently being processed
      // (at position processedCount) or still queued (after that index).
      // The branch for index < processedCount is a defensive fallback for
      // a brief window where increment_processed has run but the results
      // write has not yet been reflected in the polled response.
      if (index < processedCount) {
        status = 'done';
      } else if (index === processedCount) {
        status = 'processing';
      } else {
        status = 'pending';
      }
    } else {
      // Terminal state — files without a result entry were not reached
      // (e.g. the job failed or was cancelled mid-run).  Reflect the
      // overall job outcome so rows don't appear misleadingly as pending.
      if (job.status === 'done') {
        status = 'done';
      } else if (job.status === 'failed') {
        status = 'failed';
      } else if (job.status === 'cancelled') {
        status = 'cancelled';
      } else {
        // 'partial' or unknown terminal — unprocessed files were never
        // reached; pending is the most accurate representation.
        status = 'pending';
      }
    }
    return {
      filename,
      status,
      invoice_number: r?.invoice_number || '—',
      renamed_filename: r?.renamed_filename || '—',
      output_folder: r?.output_folder || '—',
    };
  });
}

function BulkUpload() {
  const navigate = useNavigate();
  const inputRef = useRef();
  const [files, setFiles] = useState([]);
  const [jobId, setJobId] = useState(() => localStorage.getItem('bulk_job_id') || null);
  const [job, setJob] = useState(null);
  const [rows, setRows] = useState([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [invoiceType, setInvoiceType] = useState('daily');
  const pollRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollJob = useCallback(
    async (id) => {
      try {
        const data = await getBulkJob(id);
        setJob(data);
        setRows(buildRowsFromJob(data));
        if (TERMINAL_STATUSES.has(data.status)) {
          stopPolling();
          setRunning(false);
        }
      } catch {
        stopPolling();
        setRunning(false);
      }
    },
    [stopPolling]
  );

  useEffect(() => {
    if (jobId) {
      pollJob(jobId);
      pollRef.current = setInterval(() => pollJob(jobId), POLL_INTERVAL);
    }
    return () => stopPolling();
  }, [jobId, pollJob, stopPolling]);

  const handleFiles = (e) => {
    const selected = Array.from(e.target.files).filter((f) =>
      f.name.toLowerCase().endsWith('.pdf')
    );
    setFiles(selected);
    setError(null);
  };

  const handleStart = async () => {
    if (!files.length) return;
    setRunning(true);
    setError(null);
    try {
      const data = await bulkUploadInvoices(files, invoiceType);
      localStorage.setItem('bulk_job_id', data.job_id);
      localStorage.setItem('upload_mode', 'bulk');
      setJobId(data.job_id);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Upload failed');
      setRunning(false);
    }
  };

  const handleReset = () => {
    stopPolling();
    localStorage.removeItem('bulk_job_id');
    localStorage.removeItem('upload_mode');
    setJobId(null);
    setJob(null);
    setRows([]);
    setFiles([]);
    setRunning(false);
    setError(null);
  };

  const progress = job
    ? Math.round((job.processed_count / Math.max(job.total_count, 1)) * 100)
    : 0;

  return (
    <div>
      {!jobId ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 w-full">
          <p className="text-sm text-gray-500 mb-5">{t('bulk_hint')}</p>
          <InvoiceTypeToggle value={invoiceType} onChange={setInvoiceType} />

          <div className="flex gap-3 items-center flex-wrap">
            <input
              ref={inputRef}
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={handleFiles}
            />
            <button
              onClick={() => inputRef.current?.click()}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            >
              {t('bulk_choose')}
            </button>
            {files.length > 0 && (
              <span className="text-sm text-gray-600 font-medium">{files.length} file(s) selected</span>
            )}
            <button
              onClick={handleStart}
              disabled={!files.length || running}
              className="px-6 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-40 transition-opacity hover:opacity-90"
              style={{ backgroundColor: '#009DD0' }}
            >
              {running ? t('bulk_running') : t('bulk_run')}
            </button>
          </div>
          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
              <span className="text-red-400 mt-0.5">⚠</span>
              {error}
            </div>
          )}
        </div>
      ) : (
        <div>
          {job && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-4 flex flex-wrap items-center gap-4 justify-between">
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-400">Job</span>
                <span className="font-mono text-sm font-medium text-gray-900">{jobId.slice(0, 8)}…</span>
                <span className={`px-2.5 py-0.5 text-xs rounded-full font-medium ${statusBadge(job.status)}`}>
                  {job.status}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <div className="w-32 bg-gray-100 rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full bg-blue-500 transition-all"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-600 font-medium">
                    {job.processed_count}/{job.total_count}
                  </span>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => navigate('/logs')}
                    className="px-3 py-1.5 text-xs border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    {t('bulk_view_logs')}
                  </button>
                  <button
                    onClick={handleReset}
                    className="px-3 py-1.5 text-xs border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    {t('bulk_reset')}
                  </button>
                </div>
              </div>
            </div>
          )}

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">{t('bulk_col_file')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">{t('bulk_col_status')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">{t('bulk_col_invoice_num')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Renamed Filename</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Output Folder</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rows.map((row, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs text-gray-700 max-w-xs truncate">{row.filename}</td>
                    <td className="px-4 py-3">
                      {row.status === 'processing' ? (
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(row.status)}`}>
                          <svg className="animate-spin w-3 h-3 shrink-0" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                          </svg>
                          {row.status}
                        </span>
                      ) : (
                        <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(row.status)}`}>
                          {row.status}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{row.invoice_number}</td>
                    <td className="px-4 py-3 font-mono text-xs text-blue-600 max-w-xs truncate">{row.renamed_filename}</td>
                    <td className="px-4 py-3">
                      {row.output_folder === '—' ? (
                        <span className="text-gray-400">—</span>
                      ) : row.output_folder === 'DoNotSend' ? (
                        <span className="inline-flex items-center px-2 py-0.5 text-xs rounded-full font-medium bg-amber-100 text-amber-800 border border-amber-200">
                          🚫 DoNotSend
                        </span>
                      ) : row.output_folder === 'Error' ? (
                        <span className="px-2 py-0.5 text-xs rounded-full font-medium bg-red-100 text-red-800">
                          {row.output_folder}
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 text-xs rounded-full font-medium bg-green-100 text-green-800">
                          {row.output_folder}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-10 text-center text-gray-400 text-sm">
                      Waiting for files…
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function InvoiceUploadPage() {
  useLang();
  const [mode, setMode] = useState(() => {
    const savedMode = localStorage.getItem('upload_mode');
    // Auto-switch to bulk when a bulk job exists and the user has not
    // explicitly navigated back to single mode
    if (localStorage.getItem('bulk_job_id') && savedMode !== 'single') return 'bulk';
    return savedMode || 'single';
  });

  const handleModeChange = (newMode) => {
    setMode(newMode);
    localStorage.setItem('upload_mode', newMode);
  };

  return (
    <div>
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-gray-900">{t('upload_title')}</h1>
        <p className="mt-1 text-sm text-gray-500">Process individual or batched PDF invoices through OCR extraction.</p>
      </div>
      <ImportantNotice />

      {/* Mode toggle */}
      <div className="flex gap-1 mb-6 bg-gray-100 rounded-lg p-1 max-w-xs">
        <button
          onClick={() => handleModeChange('single')}
          className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${
            mode === 'single'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Single
        </button>
        <button
          onClick={() => handleModeChange('bulk')}
          className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${
            mode === 'bulk'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Bulk
        </button>
      </div>

      {mode === 'single' ? <SingleUpload /> : <BulkUpload />}
    </div>
  );
}
