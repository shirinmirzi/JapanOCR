import React, { useState, useRef } from 'react';
import ImportantNotice from '../components/ImportantNotice';
import { uploadInvoice } from '../services/api';
import { t } from '../i18n';

const FIELD_LABELS = [
  ['invoice_number', 'invoice_number'],
  ['vendor_name', 'vendor_name'],
  ['vendor_address', 'vendor_address'],
  ['customer_name', 'customer_name'],
  ['customer_address', 'customer_address'],
  ['invoice_date', 'invoice_date'],
  ['due_date', 'due_date'],
  ['total_amount', 'total_amount'],
  ['tax_amount', 'tax_amount'],
  ['subtotal', 'subtotal'],
  ['currency', 'currency'],
];

export default function InvoiceUploadPage() {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const inputRef = useRef();

  const handleFile = (f) => {
    if (f && f.name.toLowerCase().endsWith('.pdf')) {
      setFile(f);
      setError(null);
      setResult(null);
    } else {
      setError('Only PDF files are supported.');
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    handleFile(f);
  };

  const handleProcess = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const data = await uploadInvoice(file);
      setResult(data);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Processing failed');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setResult(null);
    setError(null);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">{t('upload_title')}</h1>
      <ImportantNotice />

      {!result ? (
        <div className="bg-white rounded-xl shadow p-6 max-w-2xl">
          <div
            className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
              dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-400'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <div className="text-5xl mb-3">📄</div>
            <p className="text-gray-600">{t('upload_hint')}</p>
            {file && (
              <p className="mt-2 text-sm font-medium text-blue-600">{file.name}</p>
            )}
            <input
              ref={inputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => handleFile(e.target.files[0])}
            />
          </div>

          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="mt-4 flex gap-3">
            <button
              onClick={() => inputRef.current?.click()}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
            >
              {t('upload_choose')}
            </button>
            <button
              onClick={handleProcess}
              disabled={!file || loading}
              className="px-6 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-50 transition-opacity hover:opacity-90"
              style={{ backgroundColor: '#009DD0' }}
            >
              {loading ? t('upload_processing') : t('upload_process')}
            </button>
          </div>
        </div>
      ) : (
        <div className="max-w-2xl">
          <div className="bg-white rounded-xl shadow p-6 mb-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Invoice Data Extracted</h2>
              <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800 font-medium">
                ✓ Processed
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {FIELD_LABELS.map(([key, label]) => (
                <div key={key} className={key.includes('address') ? 'col-span-2' : ''}>
                  <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{t(label)}</p>
                  <p className="text-sm font-medium text-gray-900">{result[key] || '—'}</p>
                </div>
              ))}
            </div>
          </div>

          {result.line_items && result.line_items.length > 0 && (
            <div className="bg-white rounded-xl shadow p-6 mb-4">
              <h3 className="font-semibold text-gray-900 mb-3">{t('line_items')}</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left border-b border-gray-200">
                    <th className="pb-2 font-medium text-gray-600">Description</th>
                    <th className="pb-2 font-medium text-gray-600">Qty</th>
                    <th className="pb-2 font-medium text-gray-600">Unit Price</th>
                    <th className="pb-2 font-medium text-gray-600">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {result.line_items.map((item, i) => (
                    <tr key={i} className="border-b border-gray-100 last:border-0">
                      <td className="py-2 text-gray-900">{item.description}</td>
                      <td className="py-2 text-gray-700">{item.quantity}</td>
                      <td className="py-2 text-gray-700">{item.unit_price}</td>
                      <td className="py-2 text-gray-700">{item.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <button
            onClick={handleReset}
            className="px-6 py-2 rounded-lg text-white text-sm font-medium"
            style={{ backgroundColor: '#002F45' }}
          >
            Upload Another
          </button>
        </div>
      )}
    </div>
  );
}
