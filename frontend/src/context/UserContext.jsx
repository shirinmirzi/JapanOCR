import React, { createContext, useContext, useState, useEffect } from 'react';
import { useIsAuthenticated } from '@azure/msal-react';
import { checkAuth, isDevLogin } from '../services/api';

const defaultUserContext = {
  user: null,
  setUser: () => {},
  loading: true,
};

const UserContext = createContext(defaultUserContext);

export function UserProvider({ children }) {
  const isAuthenticated = useIsAuthenticated();
  const devAuthenticated = isDevLogin();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isAuthenticated || devAuthenticated) {
      checkAuth()
        .then((data) => setUser(data))
        .catch(() => setUser(null))
        .finally(() => setLoading(false));
    } else {
      setUser(null);
      setLoading(false);
    }
  }, [isAuthenticated, devAuthenticated]);

  return (
    <UserContext.Provider value={{ user, setUser, loading }}>
      {children}
    </UserContext.Provider>
  );
}

export const useUser = () => useContext(UserContext) || defaultUserContext;
