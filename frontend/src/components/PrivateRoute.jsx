/**
 * Japan OCR Tool - Private Route Guard
 *
 * Redirects unauthenticated users to /login before rendering protected
 * children. Accepts both MSAL-authenticated sessions and dev-login bypass.
 *
 * Key Features:
 * - Auth Check: Verifies MSAL state and dev-login flag before rendering
 * - Redirect: Sends unauthenticated visitors to /login with replace history
 *
 * Dependencies: @azure/msal-react, services/api
 * Author: SHIRIN MIRZI M K
 */
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useIsAuthenticated } from '@azure/msal-react';
import { isDevLogin } from '../services/api';

/**
 * Renders children when authenticated, otherwise redirects to /login.
 *
 * @param {Object} props - Component properties
 * @param {React.ReactNode} props.children - Protected content to render
 * @returns {JSX.Element|null} Children or a Navigate redirect element
 */
export default function PrivateRoute({ children }) {
  const isAuthenticated = useIsAuthenticated();

  if (!isAuthenticated && !isDevLogin()) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
