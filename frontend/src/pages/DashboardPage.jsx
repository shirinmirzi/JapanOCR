/**
 * Japan OCR Tool - Dashboard Page
 *
 * Displays aggregated KPI metrics, vendor bar chart, status distribution,
 * and recent invoice/job activity. Polls the backend every 15 seconds and
 * supports filtering by time range (1h / 24h / 7d / all).
 *
 * Key Features:
 * - KPI Cards: Total invoices, processed, pending, failed, success rate,
 *   DoNotSend count, and total logs — each with a coloured accent bar
 * - Vendor Chart: Horizontal bar chart of top invoice vendors
 * - Status Distribution: Breakdown of all invoice statuses
 * - Recent Invoices: Includes output-folder column with DoNotSend badge
 * - Auto Refresh: Polls every 15 s; manual refresh button also available
 *
 * Dependencies: services/api, i18n
 * Author: SHIRIN MIRZI M K
 */
import React, { useState, useEffect, useCallback } from 'react';
import { getDashboardSummary } from '../services/api';
import { t } from '../i18n';

/**
 * Returns a Tailwind CSS class string for a coloured status badge pill.
 *
 * @param {string} status - Invoice/job status key (e.g. 'done', 'failed')
 * @returns {string} Tailwind bg+text class string for the given status
 */
const statusBadge = (status) => {
  const map = {
    done:       'bg-green-100 text-green-800',
    failed:     'bg-red-100 text-red-800',
    cancelled:  'bg-gray-100 text-gray-600',
    processing: 'bg-blue-100 text-blue-800',
    queued:     'bg-yellow-100 text-yellow-800',
    processed:  'bg-green-100 text-green-800',
    pending:    'bg-yellow-100 text-yellow-800',
    deleted:    'bg-gray-100 text-gray-600',
    partial:    'bg-orange-100 text-orange-800',
    error:      'bg-red-100 text-red-800',
  };
  return map[status] || 'bg-gray-100 text-gray-600';
};

/**
 * Returns a Tailwind CSS class string for an output-folder badge pill.
 * The DoNotSend folder is highlighted in amber; Error in red; others in green.
 *
 * @param {string} folder - Output folder name (e.g. 'DoNotSend', 'Error')
 * @returns {string} Tailwind bg+text class string for the given folder
 */
const folderBadgeClass = (folder) => {
  if (!folder) return 'bg-gray-100 text-gray-500';
  const lower = folder.toLowerCase();
  if (lower === 'donotsend' || lower === 'do_not_send') return 'bg-amber-100 text-amber-800 border border-amber-200';
  if (lower === 'error') return 'bg-red-100 text-red-700';
  return 'bg-green-100 text-green-700';
};

/**
 * Renders an output-folder badge, using a special 🚫 label for DoNotSend.
 *
 * @param {string} folder - upload_folder value from the invoice record
 * @returns {JSX.Element} Styled badge element
 */
const FolderBadge = ({ folder }) => {
  if (!folder || folder === '—') return <span className="text-gray-400 text-xs">—</span>;
  const isDoNotSend = folder.toLowerCase() === 'donotsend' || folder.toLowerCase() === 'do_not_send';
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full font-medium ${folderBadgeClass(folder)}`}>
      {isDoNotSend ? '🚫 DoNotSend' : folder}
    </span>
  );
};

/**
 * Maps a KPI accent name to its Tailwind top-border utility class.
 * Explicit mapping avoids Tailwind purging dynamic class strings.
 */
const ACCENT_BORDER = {
  blue:   'border-t-blue-400',
  green:  'border-t-green-400',
  yellow: 'border-t-yellow-400',
  red:    'border-t-red-400',
  indigo: 'border-t-indigo-400',
  purple: 'border-t-purple-400',
  amber:  'border-t-amber-400',
  gray:   'border-t-gray-200',
};

/**
 * Displays a single KPI metric card with a coloured accent top border,
 * a label, primary value, and optional subtitle.
 *
 * @param {Object} props - Component properties
 * @param {string} props.label - Metric label shown above the value
 * @param {string|number} props.value - Primary metric value to display
 * @param {string} [props.sub] - Optional subtitle shown below the value
 * @param {string} [props.accent='gray'] - Accent colour key (blue|green|yellow|red|indigo|purple|amber|gray)
 * @returns {JSX.Element} Bordered metric card with accent top bar
 */
const KPI = ({ label, value, sub, accent = 'gray' }) => (
  <div className={`bg-white rounded-xl border border-gray-200 border-t-2 ${ACCENT_BORDER[accent] || ACCENT_BORDER.gray} p-5 shadow-sm`}>
    <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">{label}</p>
    <p className="text-3xl font-bold text-gray-900">{value}</p>
    {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
  </div>
);

const INVOICE_TABLE_COLS = ['Invoice #', 'Vendor', 'Total', 'Date', 'Status', 'Output'];

/**
 * Renders the dashboard with KPI cards, vendor chart, status distribution,
 * and recent invoice activity. Auto-refreshes every 15 s and supports
 * time-range filtering aligned with the Logs page controls.
 *
 * @returns {JSX.Element} Dashboard page with auto-refreshing summary panels
 */
export default function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [range, setRange] = useState('all');

  const getRangeSince = (r) => {
    if (r === 'all') return undefined;
    const now = new Date();
    const hours = r === '1h' ? 1 : r === '24h' ? 24 : 24 * 7;
    return new Date(now.getTime() - hours * 60 * 60 * 1000).toISOString();
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const since = getRangeSince(range);
      const data = await getDashboardSummary({
        jobs_limit: 5,
        invoices_limit: 5,
        failures_limit: 5,
        ...(since ? { since } : {}),
      });
      setSummary(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  if (!summary && loading) return (
    <div className="flex items-center justify-center py-20 gap-2 text-gray-400">
      <span className="animate-spin inline-block w-4 h-4 border-2 border-gray-300 border-t-gray-500 rounded-full" />
      Loading dashboard…
    </div>
  );

  const kpis = summary?.kpis || {};
  const recent = summary?.recent || {};
  const byStatus = kpis.by_status || {};
  const vendors = kpis.vendors || [];

  const totalInvoices = kpis.invoices_total || 0;
  const processed = byStatus.processed || 0;
  const pending = byStatus.pending || 0;
  const failed = byStatus.failed || 0;
  const doNotSend = kpis.do_not_send || 0;
  const successRate = totalInvoices > 0 ? Math.round((processed / totalInvoices) * 100) : 0;

  const maxVendorCount = vendors.reduce((max, v) => Math.max(max, v.count), 1);

  const formatDate = (ts) => ts ? new Date(ts).toLocaleString() : '—';

  return (
    <div>
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('dash_title')}</h1>
          <p className="mt-1 text-sm text-gray-400">Overview of processing activity.</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Time-range selector — matches Logs page compact style */}
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            {['1h', '24h', '7d', 'all'].map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                  range === r
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
          {/* Refresh button — aligned with Logs page button style */}
          <button
            onClick={load}
            disabled={loading}
            className="px-3 py-1.5 text-xs bg-white border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-700 font-medium disabled:opacity-50 transition-colors"
          >
            {loading
              ? <span className="flex items-center gap-1.5"><span className="animate-spin inline-block w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full" />{t('dash_refresh')}</span>
              : t('dash_refresh')}
          </button>
        </div>
      </div>

      {/* KPI cards — single responsive grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        <KPI label="Total Invoices" value={totalInvoices} accent="blue" />
        <KPI label="Processed" value={processed} accent="green" />
        <KPI label="Pending" value={pending} accent="yellow" />
        <KPI label="Failed" value={failed} accent="red" />
        <KPI label="Success Rate" value={`${successRate}%`} accent="indigo" />
        <KPI label="Total Logs" value={kpis.logs_total || 0} accent="purple" />
      </div>

      {/* DoNotSend KPI — shown only when there are routed-away invoices */}
      {doNotSend > 0 && (
        <div className="mb-6">
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-4 shadow-sm">
            <span className="text-2xl">🚫</span>
            <div>
              <p className="text-xs font-medium text-amber-700 uppercase tracking-wide">DoNotSend Routed</p>
              <p className="text-2xl font-bold text-amber-900">{doNotSend}</p>
            </div>
            <p className="text-xs text-amber-600 ml-2">
              {doNotSend === 1 ? 'invoice' : 'invoices'} routed to the DoNotSend folder based on master-table lookup.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Vendor bar chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h2 className="font-semibold text-gray-800 mb-4 text-sm uppercase tracking-wide">Top Vendors</h2>
          {vendors.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-sm text-gray-400">No data</p>
            </div>
          ) : (
            <div className="space-y-3">
              {vendors.slice(0, 5).map((v) => (
                <div key={v.vendor_name}>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="text-gray-700 truncate text-xs">{v.vendor_name}</span>
                    <span className="text-gray-500 ml-2 text-xs font-medium">{v.count}</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full"
                      style={{
                        width: `${(v.count / maxVendorCount) * 100}%`,
                        backgroundColor: '#009DD0',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Status distribution */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h2 className="font-semibold text-gray-800 mb-4 text-sm uppercase tracking-wide">Status Distribution</h2>
          {Object.keys(byStatus).length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-sm text-gray-400">No data</p>
            </div>
          ) : (
            <div className="space-y-3">
              {Object.entries(byStatus).map(([status, count]) => (
                <div key={status} className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 text-xs rounded-full font-medium flex-shrink-0 ${statusBadge(status)}`}>
                    {status}
                  </span>
                  <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full bg-blue-400"
                      style={{ width: `${(count / Math.max(totalInvoices, 1)) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-600 font-medium flex-shrink-0">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Invoices */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <h2 className="font-semibold text-gray-800 mb-4 text-sm uppercase tracking-wide">Recent Invoices</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left">
                {INVOICE_TABLE_COLS.map((col) => (
                  <th key={col} className="pb-2 pr-4 last:pr-0 text-xs font-medium text-gray-400 uppercase tracking-wide">{col}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {(recent.invoices || []).map((inv) => (
                <tr key={inv.id} className="hover:bg-gray-50 transition-colors">
                  <td className="py-2.5 pr-4 text-gray-900 font-medium">{inv.invoice_number || '—'}</td>
                  <td className="py-2.5 pr-4 text-gray-600">{inv.vendor_name || '—'}</td>
                  <td className="py-2.5 pr-4 text-gray-600">{inv.total_amount || '—'}</td>
                  <td className="py-2.5 pr-4 text-gray-400 text-xs">{inv.invoice_date || '—'}</td>
                  <td className="py-2.5 pr-4">
                    <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(inv.status)}`}>
                      {inv.status}
                    </span>
                  </td>
                  <td className="py-2.5">
                    <FolderBadge folder={inv.upload_folder} />
                  </td>
                </tr>
              ))}
              {(recent.invoices || []).length === 0 && (
                <tr>
                  <td colSpan={INVOICE_TABLE_COLS.length} className="py-8 text-center text-gray-400 text-sm">No invoices yet</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
