import React, { useState, useEffect, useCallback } from 'react';
import { getLogsPaged } from '../services/api';
import { t } from '../i18n';

const statusBadge = (status) => {
  const map = {
    success: 'bg-green-100 text-green-800',
    error: 'bg-red-100 text-red-800',
    failed: 'bg-red-100 text-red-800',
    timeout: 'bg-orange-100 text-orange-800',
    info: 'bg-blue-100 text-blue-800',
  };
  return map[status] || 'bg-gray-100 text-gray-600';
};

function exportCSV(items) {
  const headers = ['Timestamp', 'Filename', 'Status', 'Message', 'User'];
  const rows = items.map((r) => [
    r.timestamp, r.filename, r.status, r.message || '', r.user_id || '',
  ]);
  const csv = [headers, ...rows].map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'logs.csv';
  a.click();
  URL.revokeObjectURL(url);
}

export default function LogsPage() {
  const [data, setData] = useState({ items: [], total: 0, total_pages: 1 });
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [since, setSince] = useState('');
  const [until, setUntil] = useState('');
  const [statuses, setStatuses] = useState([]);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        page,
        page_size: 20,
        q: q || undefined,
        since: since || undefined,
        until: until || undefined,
        statuses: statuses.length ? statuses : undefined,
      };
      const result = await getLogsPaged(params);
      setData(result);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, q, since, until, statuses]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [autoRefresh, load]);

  const toggleStatus = (s) =>
    setStatuses((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]);

  const formatDate = (ts) => ts ? new Date(ts).toLocaleString() : '—';
  const STATUS_OPTIONS = ['success', 'error', 'failed', 'timeout', 'info'];

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900">{t('logs_title')}</h1>
        <div className="flex gap-2">
          <button
            onClick={() => exportCSV(data.items)}
            className="px-3 py-1.5 text-xs border border-gray-300 rounded hover:bg-gray-50"
          >
            Export CSV
          </button>
          <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            Auto-refresh
          </label>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow p-4 mb-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Search</label>
          <input
            type="text"
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(1); }}
            placeholder="filename or message…"
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 w-48"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Since</label>
          <input
            type="date"
            value={since}
            onChange={(e) => { setSince(e.target.value); setPage(1); }}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Until</label>
          <input
            type="date"
            value={until}
            onChange={(e) => { setUntil(e.target.value); setPage(1); }}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Status</label>
          <div className="flex gap-1">
            {STATUS_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => { toggleStatus(s); setPage(1); }}
                className={`px-2 py-1 text-xs rounded ${
                  statuses.includes(s) ? 'bg-blue-500 text-white' : 'border border-gray-300 hover:bg-gray-50'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <button onClick={load} className="px-4 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">
          Refresh
        </button>
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Timestamp</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Filename</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Message</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">User</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading && data.items.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>
            )}
            {!loading && data.items.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No logs found</td></tr>
            )}
            {data.items.map((log) => (
              <tr key={log.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{formatDate(log.timestamp)}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-700 max-w-xs truncate">{log.filename}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(log.status)}`}>
                    {log.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-700 max-w-sm truncate">{log.message || log.error || '—'}</td>
                <td className="px-4 py-3 text-gray-600">{log.user_id || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between text-sm text-gray-600">
        <span>Total: {data.total} logs</span>
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
