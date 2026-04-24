import React, { createContext, useContext, useState } from 'react';

const ModuleContext = createContext(null);

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

export function useModule() {
  return useContext(ModuleContext);
}
