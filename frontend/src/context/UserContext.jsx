/**
 * Japan OCR Tool - User Context
 *
 * Provides authenticated user state to the component tree. Resolves the
 * current user from the backend after MSAL or dev-login authentication
 * is confirmed.
 *
 * Key Features:
 * - Auth Bridge: Watches MSAL and dev-login state to trigger user fetch
 * - User State: Exposes user object, setter, and loading flag via context
 * - Fallback: Sets user to null on fetch failure so consumers can handle it
 *
 * Dependencies: @azure/msal-react, services/api
 * Author: SHIRIN MIRZI M K
 */
import React, { createContext, useContext, useState, useEffect } from 'react';
import { useIsAuthenticated } from '@azure/msal-react';
import { checkAuth, isDevLogin } from '../services/api';

const defaultUserContext = {
  user: null,
  setUser: () => {},
  loading: true,
};

const UserContext = createContext(defaultUserContext);

/**
 * Fetches and provides authenticated user data to all child components.
 *
 * @param {Object} props - Component properties
 * @param {React.ReactNode} props.children - Child components to wrap
 * @returns {JSX.Element} UserContext provider wrapping children
 */
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

/**
 * Returns the current user context value, falling back to defaults if unset.
 *
 * @returns {{ user: Object|null, setUser: Function, loading: boolean }}
 */
export const useUser = () => useContext(UserContext) || defaultUserContext;
