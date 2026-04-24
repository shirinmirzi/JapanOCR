import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { getLogsPaged } from '../services/api';
import { t } from '../i18n';

const MODULES = ['invoice', 'fax'];

const STATUS_OPTIONS = [
  'processing', 'success', 'processed', 'completed',
  'error', 'failed', 'not_found', 'timeout',
  'incomplete', 'cancelled', 'info',
];

// Short display labels for the compact status chips
const STATUS_CHIP_LABELS = {
  success:    'Success',
  processed:  'Processed',
  completed:  'Done',
  error:      'Error',
  failed:     'Failed',
  not_found:  'Not Found',
  timeout:    'Timeout',
  incomplete: 'Partial',
  cancelled:  'Cancelled',
  processing: 'Active',
  info:       'Info',
};

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

// A "processing" log entry is considered actively running only if it was
// created within the last 10 minutes. Entries older than that are likely
// stuck (e.g. the backend crashed before writing a terminal status), and
// should not keep the Logs page polling indefinitely.
const STALE_PROCESSING_MS = 10 * 60 * 1000;
const isActiveProcessing = (log) => {
  if (!isProcessing(log.status)) return false;
  if (!log.timestamp) return true;
  return Date.now() - new Date(log.timestamp).getTime() < STALE_PROCESSING_MS;
};

const getDatePrefix = (timestamp) => (timestamp || '').slice(0, 10) || 'unknown';

// Determine the dominant visual status for a group (drives left border color)
const groupBorderClass = (processing, failed, incomplete, complete) => {
  if (processing > 0) return 'border-l-4 border-blue-400';
  if (failed > 0) return 'border-l-4 border-red-400';
  if (incomplete > 0) return 'border-l-4 border-orange-400';
  if (complete > 0) return 'border-l-4 border-green-400';
  return 'border-l-4 border-gray-200';
};

function groupLogs(items) {
  const groups = {};
  items.forEach((log) => {
    const key = log.execution_folder
      ? `exec:${log.execution_folder}`
      : `date:${getDatePrefix(log.timestamp)}`;
    if (!groups[key]) {
      groups[key] = {
        key,
        isBatch: !!log.execution_folder,
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
  // Sort: processing groups first, then by latest timestamp desc
  return Object.values(groups).sort((a, b) => {
    const aProcessing = a.items.some((l) => isProcessing(l.status));
    const bProcessing = b.items.some((l) => isProcessing(l.status));
    if (aProcessing !== bProcessing) return aProcessing ? -1 : 1;
    return b.latest.localeCompare(a.latest);
  });
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

// Chevron SVG for expand/collapse
function Chevron({ open }) {
  return (
    <svg
      className={`w-3.5 h-3.5 text-gray-400 transition-transform duration-150 flex-shrink-0 ${open ? 'rotate-90' : ''}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2.5}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}

export default function LogsPage() {
  // Persist the selected module across page visits
  const [module, setModuleState] = useState(
    () => localStorage.getItem('logs_module') || 'invoice'
  );
  const setModule = (m) => {
    localStorage.setItem('logs_module', m);
    setModuleState(m);
    setPage(1);
  };

  const [data, setData] = useState({ items: [], total: 0, total_pages: 1 });
  const [page, setPage] = useState(1);
  // Separate UI state from debounced API state to keep input responsive
  const [qInput, setQInput] = useState('');
  const [q, setQ] = useState('');
  const [since, setSince] = useState('');
  const [until, setUntil] = useState('');
  const [statuses, setStatuses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [initialLoadDone, setInitialLoadDone] = useState(false);
  const [expanded, setExpanded] = useState(new Set());

  // Debounce the search input: update the API query 300 ms after typing stops
  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(qInput);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [qInput]);

  // Request-dedup counter: each load call gets a unique ID; stale responses
  // (where a newer call has already fired) are silently discarded so that
  // rapid typing cannot cause out-of-order result overwrites.
  const loadIdRef = useRef(0);

  const load = useCallback(async (isBackground = false) => {
    const myId = ++loadIdRef.current;
    // Only show the full loading indicator on explicit loads (initial load or
    // manual refresh), not during silent background polling.
    if (!isBackground) setLoading(true);
    try {
      const params = {
        page,
        page_size: 50,
        q: q || undefined,
        since: since || undefined,
        until: until || undefined,
        statuses: statuses.length ? statuses : undefined,
        source: module,
      };
      const result = await getLogsPaged(params);
      // Discard stale responses from superseded requests
      if (myId !== loadIdRef.current) return;
      setData(result);
      setInitialLoadDone(true);
    } catch (e) {
      if (myId === loadIdRef.current) console.error(e);
    } finally {
      if (myId === loadIdRef.current) setLoading(false);
    }
  }, [page, q, since, until, statuses, module]);

  // Keep a stable ref to the latest load function so the polling interval
  // doesn't need to be recreated every time data changes.
  const loadRef = useRef(load);
  useEffect(() => { loadRef.current = load; }, [load]);

  useEffect(() => {
    load();
  }, [load]);

  // Track when the component was first mounted so we can poll briefly even
  // when there are no active-processing entries yet.  This handles the
  // single-upload scenario where a "processing" log entry may not be visible
  // in the DB the instant the user navigates to this page.
  const mountTimeRef = useRef(Date.now());
  // How long after mount to keep polling even without active-processing entries
  const MOUNT_POLL_WINDOW_MS = 30 * 1000;

  // Auto-refresh every 3 s while there are actively-processing entries OR
  // while the page was recently mounted (so a just-started single upload
  // becomes visible quickly without requiring a manual refresh).
  useEffect(() => {
    const hasActive = data.items.some(isActiveProcessing);
    const isFreshMount = Date.now() - mountTimeRef.current < MOUNT_POLL_WINDOW_MS;
    if (!hasActive && !isFreshMount) return;
    const id = setInterval(() => loadRef.current(true), 3000);
    return () => clearInterval(id);
  }, [data.items]);

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

  const totalProcessing = data.items.filter((l) => isProcessing(l.status)).length;
  const totalComplete = data.items.filter((l) => isComplete(l.status)).length;
  const totalFailed = data.items.filter((l) => isFailed(l.status)).length;

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          {/* Module toggle — compact segmented control */}
          <div className="flex rounded-lg border border-gray-200 overflow-hidden w-fit mb-2">
            {MODULES.map((m) => (
              <button
                key={m}
                onClick={() => setModule(m)}
                className={`px-3 py-1 text-xs font-medium transition-colors ${
                  module === m
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                {t(`logs_module_${m}`)}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">{t('logs_title')}</h1>
            {loading && (
              <span className="animate-spin inline-block w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full" aria-label="loading" />
            )}
            {totalProcessing > 0 && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800">
                <span className="animate-spin inline-block w-2.5 h-2.5 border-2 border-blue-500 border-t-transparent rounded-full" />
                {totalProcessing} processing
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2 mt-1">
          <button
            onClick={() => exportCSV(data.items)}
            className="px-3 py-1.5 text-xs border border-gray-300 rounded hover:bg-gray-50"
          >
            {t('logs_export_csv')}
          </button>
          <button
            onClick={load}
            className="px-3 py-1.5 text-xs border border-gray-300 rounded hover:bg-gray-50"
          >
            {t('logs_refresh')}
          </button>
        </div>
      </div>

      {/* Summary bar */}
      {data.items.length > 0 && (
        <div className="flex items-center gap-3 mb-3 text-xs text-gray-500">
          <span>{data.total} {t('logs_total').toLowerCase()}</span>
          {totalComplete > 0 && (
            <span className="text-green-700" aria-label={`${totalComplete} complete`}>
              <span aria-hidden="true">✓</span> {totalComplete} complete
            </span>
          )}
          {totalProcessing > 0 && (
            <span className="text-blue-700" aria-label={`${totalProcessing} processing`}>
              <span aria-hidden="true">⟳</span> {totalProcessing} processing
            </span>
          )}
          {totalFailed > 0 && (
            <span className="text-red-700" aria-label={`${totalFailed} failed`}>
              <span aria-hidden="true">✗</span> {totalFailed} failed
            </span>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl shadow p-4 mb-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Search</label>
          <input
            type="text"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
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
                className={`px-2 py-0.5 text-xs rounded-full font-medium transition-colors ${
                  statuses.includes(s)
                    ? 'bg-blue-500 text-white'
                    : 'border border-gray-300 text-gray-600 hover:bg-gray-50'
                }`}
              >
                {STATUS_CHIP_LABELS[s] || s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Grouped expandable list */}
      <div className="space-y-2">
        {/* Show a subtle loading placeholder only on the very first fetch */}
        {!initialLoadDone && loading && (
          <div className="bg-white rounded-xl shadow px-6 py-8 text-center text-gray-400 flex items-center justify-center gap-2">
            <span className="animate-spin inline-block w-4 h-4 border-2 border-gray-300 border-t-gray-500 rounded-full" />
            {t('logs_loading')}
          </div>
        )}
        {initialLoadDone && data.items.length === 0 && (
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
          const borderClass = groupBorderClass(processing, failed, incomplete, complete);

          return (
            <div key={group.key} className={`bg-white rounded-xl shadow overflow-hidden ${borderClass}`}>
              {/* Group header */}
              <button
                className="w-full text-left px-4 py-3 flex items-start justify-between hover:bg-gray-50 transition-colors"
                onClick={() => toggleExpand(group.key)}
              >
                <div className="flex-1 min-w-0 mr-4">
                  <div className="flex items-center gap-2">
                    <Chevron open={isOpen} />
                    {group.isBatch ? (
                      <span className="text-gray-400 text-xs" aria-label="batch">📁</span>
                    ) : (
                      <span className="text-gray-400 text-xs" aria-label="date">📅</span>
                    )}
                    <span className="font-medium text-gray-900 truncate text-sm">{group.label}</span>
                    {processing > 0 && (
                      <span className="animate-spin inline-block w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full flex-shrink-0" />
                    )}
                  </div>
                  <div className="mt-1 ml-6 flex flex-wrap items-center gap-1.5 text-xs text-gray-500">
                    <span>{group.items.length} file{group.items.length !== 1 ? 's' : ''}</span>
                    <span className="text-gray-300">•</span>
                    <span>{formatDate(group.latest)}</span>
                    {users && (
                      <>
                        <span className="text-gray-300">•</span>
                        <span className="px-1.5 py-0.5 bg-gray-100 rounded text-gray-600 font-medium">{users}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
                  {processing > 0 && (
                    <span className="px-2 py-0.5 text-xs rounded-full font-medium bg-blue-100 text-blue-800" aria-label={`${processing} processing`}>
                      <span aria-hidden="true">⟳</span> {processing}
                    </span>
                  )}
                  {complete > 0 && (
                    <span className="px-2 py-0.5 text-xs rounded-full font-medium bg-green-100 text-green-800" aria-label={`${complete} complete`}>
                      <span aria-hidden="true">✓</span> {complete}
                    </span>
                  )}
                  {incomplete > 0 && (
                    <span className="px-2 py-0.5 text-xs rounded-full font-medium bg-orange-100 text-orange-800" aria-label={`${incomplete} incomplete`}>
                      ~ {incomplete}
                    </span>
                  )}
                  {failed > 0 && (
                    <span className="px-2 py-0.5 text-xs rounded-full font-medium bg-red-100 text-red-800" aria-label={`${failed} failed`}>
                      <span aria-hidden="true">✗</span> {failed}
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
                      className="px-4 py-2.5 flex items-start gap-3 border-b border-gray-50 last:border-0 hover:bg-gray-50"
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
                        {log.output_path && (
                          <div className="mt-0.5 text-xs text-gray-400 truncate max-w-sm font-mono">
                            {log.output_path}
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
                          {isProcessing(log.status) ? (
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

