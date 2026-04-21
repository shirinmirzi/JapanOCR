import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ImportantNotice from '../components/ImportantNotice';
import { uploadInvoice, bulkUploadInvoices, getBulkJob } from '../services/api';
import { t } from '../i18n';

// ── Invoice type toggle ────────────────────────────────────────────────────────

function InvoiceTypeToggle({ value, onChange }) {
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

const FIELD_LABELS = [
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
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [invoiceType, setInvoiceType] = useState('monthly');
  const inputRef = useRef();

  const handleFile = (f) => {
    if (f && f.name.toLowerCase().endsWith('.pdf')) {
      setFile(f);
      setError(null);
      setResult(null);
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
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Processing failed');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setResult(null);
    setError(null);
  };

  return (
    <div>
      {!result ? (
        <div className="bg-white rounded-xl shadow p-6 max-w-2xl">
          <InvoiceTypeToggle value={invoiceType} onChange={setInvoiceType} />
          <div
            className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
              dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-400'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <div className="text-5xl mb-3">📄</div>
            <p className="text-gray-600">{t('upload_hint')}</p>
            {file && (
              <p className="mt-2 text-sm font-medium text-blue-600">{file.name}</p>
            )}
            <input
              ref={inputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => handleFile(e.target.files[0])}
            />
          </div>

          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="mt-4 flex gap-3">
            <button
              onClick={() => inputRef.current?.click()}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
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
        <div className="max-w-2xl">
          <div className="bg-white rounded-xl shadow p-6 mb-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Invoice Data Extracted</h2>
              <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800 font-medium">
                ✓ Processed
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {FIELD_LABELS.map(([key, label]) => (
                <div key={key} className={key.includes('address') ? 'col-span-2' : ''}>
                  <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{t(label)}</p>
                  <p className="text-sm font-medium text-gray-900">{result[key] || '—'}</p>
                </div>
              ))}
            </div>
          </div>

          {result.line_items && result.line_items.length > 0 && (
            <div className="bg-white rounded-xl shadow p-6 mb-4">
              <h3 className="font-semibold text-gray-900 mb-3">{t('line_items')}</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left border-b border-gray-200">
                    <th className="pb-2 font-medium text-gray-600">Description</th>
                    <th className="pb-2 font-medium text-gray-600">Qty</th>
                    <th className="pb-2 font-medium text-gray-600">Unit Price</th>
                    <th className="pb-2 font-medium text-gray-600">Total</th>
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
            className="px-6 py-2 rounded-lg text-white text-sm font-medium"
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
    cancelled: 'bg-gray-100 text-gray-600',
    processing: 'bg-blue-100 text-blue-800',
    queued: 'bg-yellow-100 text-yellow-800',
    partial: 'bg-orange-100 text-orange-800',
    pending: 'bg-yellow-100 text-yellow-800',
  };
  return map[status] || 'bg-gray-100 text-gray-600';
};

function buildRowsFromJob(job) {
  if (!job) return [];
  const results = job.results || {};
  return (job.filenames || []).map((filename) => {
    const r = results[filename];
    return {
      filename,
      status: r ? r.status : (job.status === 'done' ? 'done' : 'pending'),
      invoice_number: r?.invoice_number || '—',
      vendor_name: r?.vendor_name || '—',
      total_amount: r?.total_amount || '—',
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
  const [invoiceType, setInvoiceType] = useState('monthly');
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
      setJobId(data.job_id);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Upload failed');
      setRunning(false);
    }
  };

  const handleReset = () => {
    stopPolling();
    localStorage.removeItem('bulk_job_id');
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
        <div className="bg-white rounded-xl shadow p-6 max-w-2xl">
          <p className="text-gray-600 mb-4">{t('bulk_hint')}</p>
          <InvoiceTypeToggle value={invoiceType} onChange={setInvoiceType} />
          <div className="flex gap-3 items-center">
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
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
            >
              {t('bulk_choose')}
            </button>
            {files.length > 0 && (
              <span className="text-sm text-gray-600">{files.length} file(s) selected</span>
            )}
            <button
              onClick={handleStart}
              disabled={!files.length || running}
              className="px-6 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-50"
              style={{ backgroundColor: '#009DD0' }}
            >
              {running ? t('bulk_running') : t('bulk_run')}
            </button>
          </div>
          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
              {error}
            </div>
          )}
        </div>
      ) : (
        <div>
          {job && (
            <div className="bg-white rounded-xl shadow p-4 mb-4 flex items-center justify-between">
              <div>
                <span className="text-sm text-gray-500">Job: </span>
                <span className="font-mono text-sm">{jobId.slice(0, 8)}…</span>
                <span
                  className={`ml-3 px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(job.status)}`}
                >
                  {job.status}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-32 bg-gray-200 rounded-full h-2">
                  <div
                    className="h-2 rounded-full bg-blue-500 transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <span className="text-sm text-gray-600">
                  {job.processed_count}/{job.total_count}
                </span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => navigate('/logs')}
                  className="px-3 py-1.5 text-xs border border-gray-300 rounded hover:bg-gray-50"
                >
                  {t('bulk_view_logs')}
                </button>
                <button
                  onClick={handleReset}
                  className="px-3 py-1.5 text-xs border border-gray-300 rounded hover:bg-gray-50"
                >
                  {t('bulk_reset')}
                </button>
              </div>
            </div>
          )}

          <div className="bg-white rounded-xl shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">{t('bulk_col_file')}</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">{t('bulk_col_status')}</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">{t('bulk_col_invoice_num')}</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">{t('bulk_col_vendor')}</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">{t('bulk_col_total')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rows.map((row, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs text-gray-700 max-w-xs truncate">{row.filename}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(row.status)}`}>
                        {row.status === 'processing' ? (
                          <span className="flex items-center gap-1">
                            <span className="animate-spin inline-block w-2 h-2 border border-blue-500 border-t-transparent rounded-full" />
                            {row.status}
                          </span>
                        ) : row.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{row.invoice_number}</td>
                    <td className="px-4 py-3 text-gray-700">{row.vendor_name}</td>
                    <td className="px-4 py-3 text-gray-700">{row.total_amount}</td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
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
  const [mode, setMode] = useState('single');

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">{t('upload_title')}</h1>
      <ImportantNotice />

      {/* Toggle tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 rounded-lg p-1 max-w-xs">
        <button
          onClick={() => setMode('single')}
          className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${
            mode === 'single'
              ? 'bg-white text-gray-900 shadow'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Single
        </button>
        <button
          onClick={() => setMode('bulk')}
          className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${
            mode === 'bulk'
              ? 'bg-white text-gray-900 shadow'
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
