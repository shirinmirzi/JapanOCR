import React, { useState, useEffect, useCallback } from 'react';
import { getDashboardSummary } from '../services/api';
import { t } from '../i18n';

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

const KPI = ({ label, value, sub }) => (
  <div className="bg-white rounded-xl shadow p-5">
    <p className="text-sm text-gray-500 mb-1">{label}</p>
    <p className="text-3xl font-bold text-gray-900">{value}</p>
    {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
  </div>
);

export default function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [range, setRange] = useState('all');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getDashboardSummary({ jobs_limit: 5, invoices_limit: 5, failures_limit: 5 });
      setSummary(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

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

  const activeJobs = (recent.jobs || []).filter((j) => ['queued', 'processing'].includes(j.status)).length;

  const maxVendorCount = vendors.reduce((max, v) => Math.max(max, v.count), 1);

  const formatDate = (ts) => ts ? new Date(ts).toLocaleString() : '—';

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('dash_title')}</h1>
        <div className="flex items-center gap-3">
          <div className="flex gap-1">
            {['1h', '24h', '7d', 'all'].map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-3 py-1 text-xs rounded ${
                  range === r ? 'bg-blue-500 text-white' : 'border border-gray-300 hover:bg-gray-50'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
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
      <div className="grid grid-cols-3 gap-4 mb-6">
        <KPI label="Total Jobs" value={kpis.jobs_total || 0} />
        <KPI label="Active Jobs" value={activeJobs} />
        <KPI label="Total Logs" value={kpis.logs_total || 0} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* Vendor bar chart */}
        <div className="bg-white rounded-xl shadow p-5">
          <h2 className="font-semibold text-gray-900 mb-4">Top Vendors</h2>
          {vendors.length === 0 ? (
            <p className="text-sm text-gray-400">No data</p>
          ) : (
            <div className="space-y-3">
              {vendors.slice(0, 5).map((v) => (
                <div key={v.vendor_name}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700 truncate">{v.vendor_name}</span>
                    <span className="text-gray-500 ml-2">{v.count}</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className="h-2 rounded-full"
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
        <div className="bg-white rounded-xl shadow p-5">
          <h2 className="font-semibold text-gray-900 mb-4">Status Distribution</h2>
          {Object.keys(byStatus).length === 0 ? (
            <p className="text-sm text-gray-400">No data</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(byStatus).map(([status, count]) => (
                <div key={status} className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(status)}`}>
                    {status}
                  </span>
                  <div className="flex-1 bg-gray-100 rounded-full h-2">
                    <div
                      className="h-2 rounded-full bg-blue-400"
                      style={{ width: `${(count / Math.max(totalInvoices, 1)) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-600">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Jobs */}
      <div className="bg-white rounded-xl shadow p-5 mb-6">
        <h2 className="font-semibold text-gray-900 mb-3">Recent Jobs</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left">
              <th className="pb-2 font-medium text-gray-600">ID</th>
              <th className="pb-2 font-medium text-gray-600">Status</th>
              <th className="pb-2 font-medium text-gray-600">Progress</th>
              <th className="pb-2 font-medium text-gray-600">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {(recent.jobs || []).map((job) => (
              <tr key={job.id}>
                <td className="py-2 font-mono text-xs">{job.id.slice(0, 8)}…</td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(job.status)}`}>
                    {job.status}
                  </span>
                </td>
                <td className="py-2 text-gray-700">{job.processed_count}/{job.total_count}</td>
                <td className="py-2 text-gray-500">{formatDate(job.created_at)}</td>
              </tr>
            ))}
            {(recent.jobs || []).length === 0 && (
              <tr><td colSpan={4} className="py-4 text-center text-gray-400">No jobs yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Recent Invoices */}
      <div className="bg-white rounded-xl shadow p-5">
        <h2 className="font-semibold text-gray-900 mb-3">Recent Invoices</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left">
              <th className="pb-2 font-medium text-gray-600">Invoice #</th>
              <th className="pb-2 font-medium text-gray-600">Vendor</th>
              <th className="pb-2 font-medium text-gray-600">Total</th>
              <th className="pb-2 font-medium text-gray-600">Date</th>
              <th className="pb-2 font-medium text-gray-600">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {(recent.invoices || []).map((inv) => (
              <tr key={inv.id}>
                <td className="py-2 text-gray-900">{inv.invoice_number || '—'}</td>
                <td className="py-2 text-gray-700">{inv.vendor_name || '—'}</td>
                <td className="py-2 text-gray-700">{inv.total_amount || '—'}</td>
                <td className="py-2 text-gray-500">{inv.invoice_date || '—'}</td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${statusBadge(inv.status)}`}>
                    {inv.status}
                  </span>
                </td>
              </tr>
            ))}
            {(recent.invoices || []).length === 0 && (
              <tr><td colSpan={5} className="py-4 text-center text-gray-400">No invoices yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
