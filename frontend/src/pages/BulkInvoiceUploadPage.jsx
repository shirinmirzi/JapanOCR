import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { bulkUploadInvoices, getBulkJob } from '../services/api';
import { t } from '../i18n';

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

export default function BulkInvoiceUploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef();
  const [files, setFiles] = useState([]);
  const [jobId, setJobId] = useState(() => localStorage.getItem('bulk_job_id') || null);
  const [job, setJob] = useState(null);
  const [rows, setRows] = useState([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const pollJob = async (id) => {
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
  };

  useEffect(() => {
    if (jobId) {
      pollJob(jobId);
      pollRef.current = setInterval(() => pollJob(jobId), POLL_INTERVAL);
    }
    return () => stopPolling();
  }, [jobId]);

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
      const data = await bulkUploadInvoices(files);
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
      <h1 className="text-2xl font-bold text-gray-900 mb-4">{t('bulk_title')}</h1>

      {!jobId ? (
        <div className="bg-white rounded-xl shadow p-6 max-w-2xl">
          <p className="text-gray-600 mb-4">{t('bulk_hint')}</p>
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
          {/* Job status header */}
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

          {/* File rows table */}
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
