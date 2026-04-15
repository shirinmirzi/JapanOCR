import React from 'react';
import { Navigate } from 'react-router-dom';
import { useIsAuthenticated } from '@azure/msal-react';
import { isDevLogin } from '../services/api';

export default function PrivateRoute({ children }) {
  const isAuthenticated = useIsAuthenticated();

  if (!isAuthenticated && !isDevLogin()) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
