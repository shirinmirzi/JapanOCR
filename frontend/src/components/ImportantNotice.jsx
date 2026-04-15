import React, { useState } from 'react';
import { t } from '../i18n';

export default function ImportantNotice() {
  const [open, setOpen] = useState(true);

  if (!open) return null;

  return (
    <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4 mb-6 flex items-start gap-3">
      <span className="text-yellow-500 text-xl">⚠️</span>
      <div className="flex-1">
        <p className="font-semibold text-yellow-800">{t('notice_processing_title')}</p>
        <p className="text-sm text-yellow-700 mt-1">{t('notice_processing_text')}</p>
      </div>
      <button
        type="button"
        aria-label="Dismiss notice"
        onClick={() => setOpen(false)}
        className="text-yellow-600 hover:text-yellow-800 text-lg leading-none"
      >
        ×
      </button>
    </div>
  );
}
