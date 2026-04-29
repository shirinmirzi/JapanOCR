/**
 * Japan OCR Tool - Jobs Page
 *
 * Paginated view of all bulk-upload processing jobs. Displays per-job
 * progress, status badges, and expandable file-level result details.
 * Auto-refreshes while any job is in an active state.
 *
 * Key Features:
 * - Job Table: Lists jobs with status badge, progress bar, and metadata
 * - Auto Refresh: Polls every 15 s when queued or processing jobs exist
 * - Expandable Rows: Click a row to reveal filenames and result JSON
 * - Status Filter: Dropdown to narrow the list to a specific status
 *
 * Dependencies: services/api, i18n
 * Author: SHIRIN MIRZI M K
 */
import React, { useState, useEffect, useCallback } from 'react';
import { getJobsPaged } from '../services/api';
import { t } from '../i18n';
import { useLang } from '../context/LangContext';

/**
 * Returns a Tailwind CSS class string for a colored status badge pill.
 *
 * @param {string} status - Job status key (e.g. 'done', 'failed', 'queued')
 * @returns {string} Tailwind bg+text class string for the given status
 */
const statusBadge = (status) => {
  const map = {
    done: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    cancelled: 'bg-gray-100 text-gray-600',
    interrupted: 'bg-gray-100 text-gray-600',
    processing: 'bg-blue-100 text-blue-800',
    queued: 'bg-yellow-100 text-yellow-800',
    partial: 'bg-orange-100 text-orange-800',
  };
  return map[status] || 'bg-gray-100 text-gray-600';
};

/**
 * Renders the jobs page with a paginated, filterable list of bulk-upload jobs.
 *
 * @returns {JSX.Element} Jobs table with status filter, pagination, and detail rows
 */
export default function JobsPage() {
  useLang();
  const [data, setData] = useState({ items: [], total: 0, total_pages: 1 });
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [expanded, setExpanded] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getJobsPaged({ page, page_size: 20, status: statusFilter || undefined });
      setData(result);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const hasActive = data.items.some((j) => ['queued', 'processing'].includes(j.status));
    if (!hasActive) return;
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [data.items, load]);

  const toggleExpand = (id) => setExpanded(expanded === id ? null : id);

  const formatDate = (ts) => ts ? new Date(ts).toLocaleString() : '—';

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('jobs_title')}</h1>
          <p className="mt-1 text-sm text-gray-400">Batch processing jobs and their file results.</p>
        </div>
        <div className="flex gap-3">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400"
          >
            <option value="">All statuses</option>
            {['queued', 'processing', 'done', 'failed', 'cancelled', 'partial'].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <button
            onClick={load}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Job ID</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Batch Name</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Progress</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">Created</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wide">User</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading && data.items.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-gray-400 text-sm">Loading…</td></tr>
            )}
            {!loading && data.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center">
                  <div className="text-2xl mb-1">📋</div>
                  <p className="text-gray-400 text-sm">No jobs found</p>
                </td>
              </tr>
            )}
            {data.items.map((job) => (
              <React.Fragment key={job.id}>
                <tr
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => toggleExpand(job.id)}
                >
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">{job.id.slice(0, 8)}…</td>
                  <td className="px-4 py-3 text-gray-700">{job.batch_name || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(job.status)}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 bg-gray-100 rounded-full h-1.5">
                        <div
                          className="h-1.5 rounded-full bg-blue-400 transition-all"
                          style={{ width: `${Math.round((job.processed_count / Math.max(job.total_count, 1)) * 100)}%` }}
                        />
                      </div>
                      <span className="text-gray-600 text-xs">{job.processed_count}/{job.total_count}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{formatDate(job.created_at)}</td>
                  <td className="px-4 py-3 text-gray-500">{job.user_id || '—'}</td>
                </tr>
                {expanded === job.id && (
                  <tr>
                    <td colSpan={6} className="px-4 py-3 bg-gray-50 border-b border-gray-100">
                      <div className="text-xs font-mono">
                        <p className="font-semibold mb-1 text-gray-600">Files:</p>
                        <ul className="list-disc list-inside space-y-0.5">
                          {(job.filenames || []).map((f, i) => (
                            <li key={i} className="text-gray-500">{f}</li>
                          ))}
                        </ul>
                        {job.results && (
                          <details className="mt-2">
                            <summary className="cursor-pointer text-blue-600 hover:text-blue-800">Show results JSON</summary>
                            <pre className="mt-1 p-2 bg-white rounded border text-xs overflow-auto max-h-40 text-gray-700">
                              {JSON.stringify(job.results, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="mt-5 flex items-center justify-between">
        <span className="text-sm text-gray-500">
          Total: <span className="font-medium text-gray-700">{data.total}</span> jobs
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            ← Prev
          </button>
          <span className="px-3 py-1.5 text-sm text-gray-600">{page} / {data.total_pages}</span>
          <button
            onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
            disabled={page === data.total_pages}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
