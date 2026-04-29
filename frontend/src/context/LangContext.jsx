/**
 * Japan OCR Tool - Language Context
 *
 * Provides the active UI language as React state so that all components
 * re-render with updated translations when the user switches locale.
 * Replaces the previous `window.location.reload()` approach so that page
 * state (e.g. uploaded files) is preserved across language changes.
 *
 * Key Features:
 * - Lang State: Exposes the current language code and a setter via context
 * - Persistence: Delegates storage to the i18n module (localStorage 'lang')
 * - Re-render: Components that call useLang() re-render on locale change
 *
 * Dependencies: React, i18n
 * Author: SHIRIN MIRZI M K
 */
import React, { createContext, useContext, useState } from 'react';
import { getLang, setLang as i18nSetLang } from '../i18n';

const LangContext = createContext({ lang: 'en', setLang: () => {} });

/**
 * Provides the active language and a setter to all child components.
 *
 * @param {Object} props - Component properties
 * @param {React.ReactNode} props.children - Child components to wrap
 * @returns {JSX.Element} LangContext provider wrapping children
 */
export function LangProvider({ children }) {
  const [lang, setLangState] = useState(getLang);

  const changeLang = (l) => {
    i18nSetLang(l);
    setLangState(l);
  };

  return (
    <LangContext.Provider value={{ lang, setLang: changeLang }}>
      {children}
    </LangContext.Provider>
  );
}

/**
 * Consumes LangContext. Calling this hook inside a component subscribes it
 * to language changes so it re-renders whenever the locale is switched.
 *
 * @returns {{ lang: string, setLang: Function }} Active language and setter
 */
export const useLang = () => useContext(LangContext);
