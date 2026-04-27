/**
 * Japan OCR Tool - Dashboard Page
 *
 * Displays aggregated KPI metrics, vendor bar chart, status distribution,
 * and recent invoice/job activity. Polls the backend every 15 seconds and
 * supports filtering by time range (1h / 24h / 7d / all).
 *
 * Key Features:
 * - KPI Cards: Total invoices, processed, pending, failed, and success rate
 * - Vendor Chart: Horizontal bar chart of top invoice vendors
 * - Status Distribution: Breakdown of all invoice statuses
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
    done: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    cancelled: 'bg-gray-100 text-gray-600',
    processing: 'bg-blue-100 text-blue-800',
    queued: 'bg-yellow-100 text-yellow-800',
    processed: 'bg-green-100 text-green-800',
    pending: 'bg-yellow-100 text-yellow-800',
    deleted: 'bg-gray-100 text-gray-600',
    partial: 'bg-orange-100 text-orange-800',
  };
  return map[status] || 'bg-gray-100 text-gray-600';
};

/**
 * Displays a single KPI metric card with a label, primary value, and subtitle.
 *
 * @param {Object} props - Component properties
 * @param {string} props.label - Metric label shown above the value
 * @param {string|number} props.value - Primary metric value to display
 * @param {string} [props.sub] - Optional subtitle shown below the value
 * @returns {JSX.Element} Bordered metric card
 */
const KPI = ({ label, value, sub }) => (
  <div className="bg-white rounded-xl border border-gray-200 p-5">
    <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">{label}</p>
    <p className="text-3xl font-bold text-gray-900">{value}</p>
    {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
  </div>
);

/**
 * Renders the dashboard with KPI cards, vendor chart, and recent activity.
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

  if (!summary && loading) return <div className="text-center py-20 text-gray-400">Loading dashboard…</div>;

  const kpis = summary?.kpis || {};
  const recent = summary?.recent || {};
  const byStatus = kpis.by_status || {};
  const vendors = kpis.vendors || [];

  const totalInvoices = kpis.invoices_total || 0;
  const processed = byStatus.processed || 0;
  const pending = byStatus.pending || 0;
  const failed = byStatus.failed || 0;
  const successRate = totalInvoices > 0 ? Math.round((processed / totalInvoices) * 100) : 0;

  const maxVendorCount = vendors.reduce((max, v) => Math.max(max, v.count), 1);

  const formatDate = (ts) => ts ? new Date(ts).toLocaleString() : '—';

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('dash_title')}</h1>
          <p className="mt-1 text-sm text-gray-400">Overview of processing activity.</p>
        </div>
        <div className="flex items-center gap-3">
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
          <button
            onClick={load}
            disabled={loading}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            {t('dash_refresh')}
          </button>
        </div>
      </div>

      {/* KPI Row 1 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
        <KPI label="Total Invoices" value={totalInvoices} />
        <KPI label="Processed" value={processed} />
        <KPI label="Pending" value={pending} />
        <KPI label="Failed" value={failed} />
        <KPI label="Success Rate" value={`${successRate}%`} />
      </div>

      {/* KPI Row 2 */}
      <div className="grid grid-cols-1 gap-4 mb-6">
        <KPI label="Total Logs" value={kpis.logs_total || 0} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Vendor bar chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="font-semibold text-gray-900 mb-4 text-sm">Top Vendors</h2>
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
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="font-semibold text-gray-900 mb-4 text-sm">Status Distribution</h2>
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
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="font-semibold text-gray-900 mb-4 text-sm">Recent Invoices</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left">
              <th className="pb-2 text-xs font-medium text-gray-400 uppercase tracking-wide">Invoice #</th>
              <th className="pb-2 text-xs font-medium text-gray-400 uppercase tracking-wide">Vendor</th>
              <th className="pb-2 text-xs font-medium text-gray-400 uppercase tracking-wide">Total</th>
              <th className="pb-2 text-xs font-medium text-gray-400 uppercase tracking-wide">Date</th>
              <th className="pb-2 text-xs font-medium text-gray-400 uppercase tracking-wide">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {(recent.invoices || []).map((inv) => (
              <tr key={inv.id}>
                <td className="py-2 text-gray-900 font-medium">{inv.invoice_number || '—'}</td>
                <td className="py-2 text-gray-600">{inv.vendor_name || '—'}</td>
                <td className="py-2 text-gray-600">{inv.total_amount || '—'}</td>
                <td className="py-2 text-gray-400 text-xs">{inv.invoice_date || '—'}</td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(inv.status)}`}>
                    {inv.status}
                  </span>
                </td>
              </tr>
            ))}
            {(recent.invoices || []).length === 0 && (
              <tr><td colSpan={5} className="py-6 text-center text-gray-400 text-sm">No invoices yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
