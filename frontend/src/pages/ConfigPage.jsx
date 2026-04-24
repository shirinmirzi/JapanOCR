import React, { useRef, useState } from 'react';
import { uploadMasterData } from '../services/api';
import { t } from '../i18n';

const MASTER_TYPES = [
  { value: 'daily', labelKey: 'config_master_daily' },
  { value: 'monthly', labelKey: 'config_master_monthly' },
];

const ACCEPTED_EXTENSIONS = ['.xlsx', '.xlsm', '.csv'];

export default function ConfigPage() {
  const [masterType, setMasterType] = useState('daily');
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const selected = e.target.files[0] || null;
    setFile(selected);
    setResult(null);
    setError(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0] || null;
    setFile(dropped);
    setResult(null);
    setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError(t('config_no_file'));
      return;
    }
    setUploading(true);
    setResult(null);
    setError(null);
    try {
      const data = await uploadMasterData(masterType, file);
      setResult(data);
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        'Upload failed';
      setError(detail);
    } finally {
      setUploading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <h1 className="text-2xl font-bold text-gray-800 mb-1">{t('config_title')}</h1>
      <p className="text-sm text-gray-500 mb-6">{t('config_hint')}</p>

      <form onSubmit={handleSubmit} className="space-y-5 bg-white rounded-xl border border-gray-200 p-6">
        {/* Master type selector */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
            {t('config_master_type')}
          </label>
          <div className="inline-flex rounded-lg border border-gray-200 p-0.5 bg-gray-50 gap-1">
            {MASTER_TYPES.map((mt) => (
              <button
                key={mt.value}
                type="button"
                onClick={() => { setMasterType(mt.value); setResult(null); setError(null); }}
                className={`py-1.5 px-4 rounded-md text-sm font-medium transition-all ${
                  masterType === mt.value
                    ? 'bg-white text-gray-900 shadow-sm border border-gray-200'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {t(mt.labelKey)}
              </button>
            ))}
          </div>
        </div>

        {/* File drop zone */}
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current && fileInputRef.current.click()}
          className="cursor-pointer border-2 border-dashed border-gray-200 rounded-lg p-8 text-center hover:border-blue-400 hover:bg-blue-50/30 transition-colors"
        >
          {file ? (
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-800 truncate">{file.name}</p>
              <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
          ) : (
            <div className="space-y-2">
              <svg
                className="mx-auto h-10 w-10 text-gray-300"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                />
              </svg>
              <p className="text-sm text-gray-500">{t('config_choose_file')}</p>
              <p className="text-xs text-gray-400">{t('config_file_accepted')}</p>
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(',')}
            onChange={handleFileChange}
            className="hidden"
          />
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            type="submit"
            disabled={uploading || !file}
            className="flex-1 py-2 px-4 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {uploading ? t('config_uploading') : t('config_upload_btn')}
          </button>
          {(file || result || error) && (
            <button
              type="button"
              onClick={handleReset}
              className="py-2 px-4 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
            >
              {t('config_reset')}
            </button>
          )}
        </div>
      </form>

      {/* Error */}
      {error && (
        <div className="mt-4 p-4 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Success result */}
      {result && (
        <div className="mt-4 rounded-xl border border-green-200 bg-green-50 p-5 space-y-3">
          <p className="font-medium text-green-800">
            ✓ {t('config_success')}
          </p>
          <div className="flex gap-4 text-sm text-green-700">
            <span>
              <strong>{result.inserted}</strong> {t('config_inserted')}
            </span>
            {result.skipped > 0 && (
              <span>
                <strong>{result.skipped}</strong> {t('config_skipped')}
              </span>
            )}
          </div>

          {result.invalid_rows && result.invalid_rows.length > 0 && (
            <div>
              <p className="text-sm font-medium text-red-700 mb-2">{t('config_invalid_rows')}</p>
              <div className="overflow-x-auto">
                <table className="text-xs w-full border-collapse">
                  <thead>
                    <tr className="bg-red-100 text-red-800">
                      <th className="text-left px-3 py-1 border border-red-200">{t('config_row')}</th>
                      <th className="text-left px-3 py-1 border border-red-200">{t('config_reason')}</th>
                      <th className="text-left px-3 py-1 border border-red-200">customer_cd</th>
                      <th className="text-left px-3 py-1 border border-red-200">destination_cd</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.invalid_rows.map((ir) => (
                      <tr key={ir.row} className="bg-white">
                        <td className="px-3 py-1 border border-red-100">{ir.row}</td>
                        <td className="px-3 py-1 border border-red-100">{ir.reason}</td>
                        <td className="px-3 py-1 border border-red-100">{ir.data?.customer_cd ?? ''}</td>
                        <td className="px-3 py-1 border border-red-100">{ir.data?.destination_cd ?? ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
