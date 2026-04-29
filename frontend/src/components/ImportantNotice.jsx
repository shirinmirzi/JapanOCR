/**
 * Japan OCR Tool - Important Notice Banner
 *
 * Displays a dismissible amber alert at the top of pages to communicate
 * processing guidelines and file-size constraints to the user.
 *
 * Key Features:
 * - Dismissible: User can close the banner; state is local (not persisted)
 * - i18n: Banner copy is drawn from the translation layer
 *
 * Dependencies: i18n
 * Author: SHIRIN MIRZI M K
 */
import React, { useState } from 'react';
import { t } from '../i18n';
import { useLang } from '../context/LangContext';

/**
 * Renders a dismissible amber notice banner with processing guidelines.
 *
 * @returns {JSX.Element|null} The notice banner, or null once dismissed
 */
export default function ImportantNotice() {
  useLang();
  const [open, setOpen] = useState(true);

  if (!open) return null;

  return (
    <div className="flex items-start gap-3 p-4 mb-5 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-800">
      <svg className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
      </svg>
      <div className="flex-1">
        <p className="font-semibold text-amber-900">{t('notice_processing_title')}</p>
        <p className="text-xs text-amber-700 mt-0.5">{t('notice_processing_text')}</p>
      </div>
      <button
        type="button"
        aria-label="Dismiss notice"
        onClick={() => setOpen(false)}
        className="text-amber-500 hover:text-amber-700 transition-colors"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
