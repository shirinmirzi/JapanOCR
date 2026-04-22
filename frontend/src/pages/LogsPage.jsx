import React, { useState, useEffect, useCallback } from 'react';
import { getLogsPaged } from '../services/api';
import { t } from '../i18n';

const STATUS_OPTIONS = [
  'success', 'error', 'failed', 'timeout', 'info',
  'processed', 'not_found', 'completed', 'incomplete', 'cancelled', 'processing',
];

const statusBadge = (status) => {
  const map = {
    success:    'bg-green-100 text-green-800',
    processed:  'bg-green-100 text-green-800',
    completed:  'bg-green-100 text-green-800',
    done:       'bg-green-100 text-green-800',
    error:      'bg-red-100 text-red-800',
    failed:     'bg-red-100 text-red-800',
    not_found:  'bg-red-100 text-red-800',
    incomplete: 'bg-orange-100 text-orange-800',
    timeout:    'bg-orange-100 text-orange-800',
    partial:    'bg-orange-100 text-orange-800',
    processing: 'bg-blue-100 text-blue-800',
    info:       'bg-blue-100 text-blue-800',
    cancelled:  'bg-gray-100 text-gray-600',
    queued:     'bg-yellow-100 text-yellow-800',
    pending:    'bg-yellow-100 text-yellow-800',
  };
  return map[status] || 'bg-gray-100 text-gray-600';
};

function exportCSV(items) {
  const headers = [
    t('logs_col_timestamp'),
    t('logs_col_filename'),
    t('logs_col_renamed'),
    t('logs_col_folder'),
    t('logs_col_status'),
    t('logs_col_message'),
    t('logs_col_user'),
  ];
  const rows = items.map((r) => [
    r.timestamp,
    r.filename,
    r.renamed_filename || '',
    r.folder_name || '',
    r.status,
    r.message || r.error || '',
    r.user_id || '',
  ]);
  const csv = [headers, ...rows]
    .map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(','))
    .join('\n');
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
    setStatuses((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );

  const formatDate = (ts) => (ts ? new Date(ts).toLocaleString() : '—');

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900">{t('logs_title')}</h1>
        <div className="flex gap-2">
          <button
            onClick={() => exportCSV(data.items)}
            className="px-3 py-1.5 text-xs border border-gray-300 rounded hover:bg-gray-50"
          >
            {t('logs_export_csv')}
          </button>
          <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            {t('logs_auto_refresh')}
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
            placeholder={t('logs_search_placeholder')}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 w-48"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('logs_filter_since')}</label>
          <input
            type="date"
            value={since}
            onChange={(e) => { setSince(e.target.value); setPage(1); }}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('logs_filter_until')}</label>
          <input
            type="date"
            value={until}
            onChange={(e) => { setUntil(e.target.value); setPage(1); }}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('logs_filter_status')}</label>
          <div className="flex flex-wrap gap-1">
            {STATUS_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => { toggleStatus(s); setPage(1); }}
                className={`px-2 py-1 text-xs rounded ${
                  statuses.includes(s)
                    ? 'bg-blue-500 text-white'
                    : 'border border-gray-300 hover:bg-gray-50'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={load}
          className="px-4 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          {t('logs_refresh')}
        </button>
      </div>

      {/* Batch-style log table */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">{t('logs_col_timestamp')}</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">{t('logs_col_filename')}</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">{t('logs_col_renamed')}</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">{t('logs_col_folder')}</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">{t('logs_col_status')}</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">{t('logs_col_message')}</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">{t('logs_col_user')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading && data.items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  {t('logs_loading')}
                </td>
              </tr>
            )}
            {!loading && data.items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  {t('logs_no_results')}
                </td>
              </tr>
            )}
            {data.items.map((log) => (
              <tr key={log.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                  {formatDate(log.timestamp)}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-700 max-w-xs truncate">
                  {log.filename || '—'}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-blue-700 max-w-xs truncate">
                  {log.renamed_filename || <span className="text-gray-400">—</span>}
                </td>
                <td className="px-4 py-3">
                  {log.folder_name ? (
                    <span
                      className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                        log.folder_name === 'Error'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-green-100 text-green-800'
                      }`}
                    >
                      {log.folder_name}
                    </span>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(log.status)}`}
                  >
                    {log.status === 'processing' ? (
                      <span className="flex items-center gap-1">
                        <span className="animate-spin inline-block w-2 h-2 border border-blue-500 border-t-transparent rounded-full" />
                        {log.status}
                      </span>
                    ) : (
                      log.status
                    )}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-700 max-w-sm truncate">
                  {log.message || log.error || '—'}
                </td>
                <td className="px-4 py-3 text-gray-600">{log.user_id || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="mt-4 flex items-center justify-between text-sm text-gray-600">
        <span>{t('logs_total')}: {data.total} logs</span>
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
