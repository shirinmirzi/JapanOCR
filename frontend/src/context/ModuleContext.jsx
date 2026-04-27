/**
 * Japan OCR Tool - Module Context
 *
 * Tracks which processing module (invoice / fax) is currently active and
 * persists the selection across page reloads via localStorage.
 *
 * Key Features:
 * - Module State: Exposes active module and a setter to switch between modules
 * - Persistence: Stores the selected module in localStorage under 'app_module'
 * - Guard: useModule throws when accessed outside a ModuleProvider
 *
 * Dependencies: React
 * Author: SHIRIN MIRZI M K
 */
import React, { createContext, useContext, useState } from 'react';

const ModuleContext = createContext(null);

/**
 * Stores the active module selection and persists it across reloads.
 *
 * @param {Object} props - Component properties
 * @param {React.ReactNode} props.children - Child components to wrap
 * @returns {JSX.Element} ModuleContext provider wrapping children
 */
export function ModuleProvider({ children }) {
  const [module, setModuleState] = useState(
    () => localStorage.getItem('app_module') || 'invoice'
  );

  const setModule = (m) => {
    localStorage.setItem('app_module', m);
    setModuleState(m);
  };

  return (
    <ModuleContext.Provider value={{ module, setModule }}>
      {children}
    </ModuleContext.Provider>
  );
}

/**
 * Consumes ModuleContext; throws if called outside a ModuleProvider.
 *
 * @returns {{ module: string, setModule: Function }} Active module and setter
 */
export function useModule() {
  const ctx = useContext(ModuleContext);
  if (!ctx) {
    throw new Error('useModule must be used within a ModuleProvider');
  }
  return ctx;
}
