import React, { useState, useEffect, useCallback } from 'react';
import { getJobsPaged } from '../services/api';
import { t } from '../i18n';

const statusBadge = (status) => {
  const map = {
    done: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    cancelled: 'bg-gray-100 text-gray-600',
    processing: 'bg-blue-100 text-blue-800',
    queued: 'bg-yellow-100 text-yellow-800',
    partial: 'bg-orange-100 text-orange-800',
  };
  return map[status] || 'bg-gray-100 text-gray-600';
};

export default function JobsPage() {
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
    const hasActive = data.items.some((j) => ['queued', 'processing'].includes(j.status));
    if (hasActive) {
      const id = setInterval(load, 15000);
      return () => clearInterval(id);
    }
  }, [load]);

  const toggleExpand = (id) => setExpanded(expanded === id ? null : id);

  const formatDate = (ts) => ts ? new Date(ts).toLocaleString() : '—';

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900">{t('jobs_title')}</h1>
        <div className="flex gap-3">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2"
          >
            <option value="">All statuses</option>
            {['queued', 'processing', 'done', 'failed', 'cancelled', 'partial'].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <button onClick={load} className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">
            Refresh
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Job ID</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Batch Name</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Progress</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Created</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">User</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading && data.items.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>
            )}
            {!loading && data.items.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No jobs found</td></tr>
            )}
            {data.items.map((job) => (
              <React.Fragment key={job.id}>
                <tr
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => toggleExpand(job.id)}
                >
                  <td className="px-4 py-3 font-mono text-xs">{job.id.slice(0, 8)}…</td>
                  <td className="px-4 py-3 text-gray-700">{job.batch_name || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(job.status)}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-gray-700">{job.processed_count}/{job.total_count}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{formatDate(job.created_at)}</td>
                  <td className="px-4 py-3 text-gray-600">{job.user_id || '—'}</td>
                </tr>
                {expanded === job.id && (
                  <tr>
                    <td colSpan={6} className="px-4 py-3 bg-gray-50">
                      <div className="text-xs font-mono">
                        <p className="font-semibold mb-1 text-gray-700">Files:</p>
                        <ul className="list-disc list-inside space-y-0.5">
                          {(job.filenames || []).map((f, i) => (
                            <li key={i} className="text-gray-600">{f}</li>
                          ))}
                        </ul>
                        {job.results && (
                          <details className="mt-2">
                            <summary className="cursor-pointer text-blue-600">Show results JSON</summary>
                            <pre className="mt-1 p-2 bg-white rounded border text-xs overflow-auto max-h-40">
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
      <div className="mt-4 flex items-center justify-between text-sm text-gray-600">
        <span>Total: {data.total} jobs</span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 border border-gray-300 rounded disabled:opacity-40 hover:bg-gray-50"
          >
            ← Prev
          </button>
          <span className="px-3 py-1.5">Page {page} / {data.total_pages}</span>
          <button
            onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
            disabled={page === data.total_pages}
            className="px-3 py-1.5 border border-gray-300 rounded disabled:opacity-40 hover:bg-gray-50"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
