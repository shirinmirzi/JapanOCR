import React, { useRef, useState } from 'react';
import { uploadMasterData } from '../services/api';
import { t } from '../i18n';

const ACCEPT = '.xlsx,.xls,.csv';

function UploadIcon() {
  return (
    <svg className="w-8 h-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

function MasterUploadCard({ type, title, description }) {
  const inputRef = useRef();
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFile = (f) => {
    if (!f) return;
    const ext = f.name.toLowerCase().split('.').pop();
    if (!['xlsx', 'xls', 'csv'].includes(ext)) {
      setError('Only .xlsx, .xls, or .csv files are accepted.');
      return;
    }
    setFile(f);
    setError(null);
    setResult(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await uploadMasterData(file, type);
      setResult(data);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Upload failed.');
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
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      {/* Card header */}
      <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
            type === 'daily' ? 'bg-blue-50 text-blue-600' : 'bg-purple-50 text-purple-600'
          }`}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h1.5C5.496 19.5 6 18.996 6 18.375m-3.75.125V5.625c0-.621.504-1.125 1.125-1.125H15a1.125 1.125 0 011.125 1.125v13.5m-12.75 0h12.75m0 0v-13.5M6 18.375V6m12.75 13.125v-1.5c0-.621-.504-1.125-1.125-1.125H12.75" />
          </svg>
        </div>
        <div>
          <h3 className="font-semibold text-gray-900 text-sm">{title}</h3>
          <p className="text-xs text-gray-500 mt-0.5">{description}</p>
        </div>
      </div>

      {/* Card body */}
      <div className="p-6">
        {result ? (
          <div className="space-y-3">
            <div className="flex items-start gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center flex-shrink-0 mt-0.5 text-white">
                <CheckIcon />
              </div>
              <div>
                <p className="text-sm font-medium text-green-800">{t('config_success')}</p>
                {result.rows_imported != null && (
                  <p className="text-xs text-green-700 mt-0.5">
                    {result.rows_imported} {t('config_rows_imported')}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={handleReset}
              className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
            >
              ← Upload another file
            </button>
          </div>
        ) : (
          <>
            {/* Drop zone */}
            <div
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                dragging
                  ? 'border-blue-400 bg-blue-50'
                  : file
                  ? 'border-green-400 bg-green-50'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              }`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
            >
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPT}
                className="hidden"
                onChange={(e) => handleFile(e.target.files[0])}
              />
              {file ? (
                <div className="flex flex-col items-center gap-2">
                  <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                    <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <p className="text-sm font-medium text-gray-900">{file.name}</p>
                  <p className="text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); handleReset(); }}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <UploadIcon />
                  <p className="text-sm text-gray-600">
                    Drag &amp; drop or{' '}
                    <span className="text-blue-600 font-medium">click to browse</span>
                  </p>
                  <p className="text-xs text-gray-400">.xlsx · .xls · .csv — UTF-8, Japanese OK</p>
                </div>
              )}
            </div>

            {error && (
              <div className="mt-3 flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                <svg className="w-4 h-4 mt-0.5 flex-shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
                {error}
              </div>
            )}

            <div className="mt-4 flex items-center gap-3">
              <button
                onClick={() => inputRef.current?.click()}
                className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-700 transition-colors"
              >
                {t('config_choose_file')}
              </button>
              <button
                onClick={handleUpload}
                disabled={!file || loading}
                className="px-5 py-2 rounded-lg text-white text-sm font-medium transition-opacity disabled:opacity-40"
                style={{ backgroundColor: !file || loading ? undefined : '#009DD0' }}
              >
                {loading ? t('config_uploading') : t('config_upload_btn')}
              </button>
              {loading && (
                <span className="animate-spin inline-block w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full" />
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function ConfigPage() {
  return (
    <div>
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('config_title')}</h1>
        <p className="mt-1 text-sm text-gray-500">{t('config_subtitle')}</p>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-3 p-4 mb-6 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-800">
        <svg className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
        </svg>
        {t('config_hint')}
      </div>

      {/* Upload cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MasterUploadCard
          type="daily"
          title={t('config_daily_title')}
          description={t('config_daily_desc')}
        />
        <MasterUploadCard
          type="monthly"
          title={t('config_monthly_title')}
          description={t('config_monthly_desc')}
        />
      </div>
    </div>
  );
}
