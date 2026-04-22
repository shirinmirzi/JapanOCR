import React, { useState, useEffect, useCallback, useMemo } from 'react';
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

const folderBadge = (folderName) => {
  if (!folderName) return 'bg-gray-100 text-gray-500';
  const lower = folderName.toLowerCase();
  if (lower === 'error') return 'bg-red-100 text-red-700';
  if (lower === 'donotsend' || lower === 'do_not_send') return 'bg-yellow-100 text-yellow-700';
  return 'bg-green-100 text-green-700';
};

const isComplete = (s) => !!s && ['success', 'processed', 'completed', 'done'].includes(s);
const isFailed = (s) => !!s && ['error', 'failed', 'not_found', 'timeout'].includes(s);
const isProcessing = (s) => !!s && ['processing', 'queued', 'pending'].includes(s);
const isIncomplete = (s) => !!s && ['incomplete', 'partial', 'cancelled'].includes(s);

const getDatePrefix = (timestamp) => (timestamp || '').slice(0, 10) || 'unknown';

function groupLogs(items) {
  const groups = {};
  items.forEach((log) => {
    const key = log.execution_folder
      ? `exec:${log.execution_folder}`
      : `date:${getDatePrefix(log.timestamp)}`;
    if (!groups[key]) {
      groups[key] = {
        key,
        label: log.execution_folder || getDatePrefix(log.timestamp) || 'Unknown',
        items: [],
        latest: log.timestamp || '',
        userIds: new Set(),
      };
    }
    groups[key].items.push(log);
    if ((log.timestamp || '') > groups[key].latest) groups[key].latest = log.timestamp;
    if (log.user_id) groups[key].userIds.add(log.user_id);
  });
  return Object.values(groups).sort((a, b) => b.latest.localeCompare(a.latest));
}

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
  const [expanded, setExpanded] = useState(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        page,
        page_size: 50,
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

  const toggleExpand = (key) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const formatDate = (ts) => (ts ? new Date(ts).toLocaleString() : '—');

  const groups = useMemo(() => groupLogs(data.items), [data.items]);

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

      {/* Grouped expandable list */}
      <div className="space-y-2">
        {loading && data.items.length === 0 && (
          <div className="bg-white rounded-xl shadow px-6 py-10 text-center text-gray-400">
            {t('logs_loading')}
          </div>
        )}
        {!loading && data.items.length === 0 && (
          <div className="bg-white rounded-xl shadow px-6 py-10 text-center text-gray-400">
            {t('logs_no_results')}
          </div>
        )}
        {groups.map((group) => {
          const isOpen = expanded.has(group.key);
          const complete = group.items.filter((l) => isComplete(l.status)).length;
          const failed = group.items.filter((l) => isFailed(l.status)).length;
          const processing = group.items.filter((l) => isProcessing(l.status)).length;
          const incomplete = group.items.filter((l) => isIncomplete(l.status)).length;
          const users = [...group.userIds].slice(0, 2).join(', ');

          return (
            <div key={group.key} className="bg-white rounded-xl shadow overflow-hidden">
              {/* Group header */}
              <button
                className="w-full text-left px-5 py-3.5 flex items-start justify-between hover:bg-gray-50 transition-colors"
                onClick={() => toggleExpand(group.key)}
              >
                <div className="flex-1 min-w-0 mr-4">
                  <div className="flex items-center gap-2">
                    <span
                      className="text-gray-400 text-xs inline-block transition-transform"
                      style={{ transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}
                    >
                      ▶
                    </span>
                    <span className="font-medium text-gray-900 truncate">{group.label}</span>
                  </div>
                  <div className="mt-0.5 ml-5 flex flex-wrap items-center gap-2 text-xs text-gray-500">
                    <span>{group.items.length} file{group.items.length !== 1 ? 's' : ''}</span>
                    <span>•</span>
                    <span>{formatDate(group.latest)}</span>
                    {users && (
                      <>
                        <span>•</span>
                        <span className="px-1.5 py-0.5 bg-gray-100 rounded text-gray-600">{users}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
                  {processing > 0 && (
                    <span className="px-2 py-0.5 text-xs rounded-full font-medium bg-blue-100 text-blue-800 flex items-center gap-1">
                      <span className="animate-spin inline-block w-2 h-2 border border-blue-500 border-t-transparent rounded-full" />
                      {processing}
                    </span>
                  )}
                  {complete > 0 && (
                    <span className="px-2 py-0.5 text-xs rounded-full font-medium bg-green-100 text-green-800">
                      ✓ {complete}
                    </span>
                  )}
                  {incomplete > 0 && (
                    <span className="px-2 py-0.5 text-xs rounded-full font-medium bg-orange-100 text-orange-800">
                      ~ {incomplete}
                    </span>
                  )}
                  {failed > 0 && (
                    <span className="px-2 py-0.5 text-xs rounded-full font-medium bg-red-100 text-red-800">
                      ✗ {failed}
                    </span>
                  )}
                </div>
              </button>

              {/* Expanded file entries */}
              {isOpen && (
                <div className="border-t border-gray-100">
                  {group.items.map((log) => (
                    <div
                      key={log.id}
                      className="px-5 py-2.5 flex items-start gap-3 border-b border-gray-50 last:border-0 hover:bg-gray-50"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs text-gray-700 truncate max-w-xs">
                            {log.filename || '—'}
                          </span>
                          {log.renamed_filename && log.renamed_filename !== log.filename && (
                            <>
                              <span className="text-gray-400 text-xs">→</span>
                              <span className="font-mono text-xs text-blue-700 truncate max-w-xs">
                                {log.renamed_filename}
                              </span>
                            </>
                          )}
                        </div>
                        {(log.message || log.error) && (
                          <div className="mt-0.5 text-xs text-gray-500 truncate max-w-sm">
                            {log.message || log.error}
                          </div>
                        )}
                        <div className="mt-0.5 text-xs text-gray-400">{formatDate(log.timestamp)}</div>
                      </div>
                      <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
                        {log.folder_name && (
                          <span className={`px-2 py-0.5 text-xs rounded font-medium ${folderBadge(log.folder_name)}`}>
                            {log.folder_name}
                          </span>
                        )}
                        <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(log.status)}`}>
                          {log.status === 'processing' ? (
                            <span className="flex items-center gap-1">
                              <span className="animate-spin inline-block w-2 h-2 border border-blue-500 border-t-transparent rounded-full" />
                              {log.status}
                            </span>
                          ) : (
                            log.status
                          )}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
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
