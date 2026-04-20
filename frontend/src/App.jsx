import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MsalProvider } from '@azure/msal-react';
import { msalInstance } from './msalConfig';
import { UserProvider } from './context/UserContext';
import PrivateRoute from './components/PrivateRoute';
import MainLayout from './layouts/MainLayout';
import LoginPage from './pages/LoginPage';
import InvoiceUploadPage from './pages/InvoiceUploadPage';
import JobsPage from './pages/JobsPage';
import LogsPage from './pages/LogsPage';
import DashboardPage from './pages/DashboardPage';

export default function App() {
  return (
    <MsalProvider instance={msalInstance}>
      <UserProvider>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <PrivateRoute>
                  <MainLayout />
                </PrivateRoute>
              }
            >
              <Route index element={<Navigate to="/upload" replace />} />
              <Route path="upload" element={<InvoiceUploadPage />} />
              <Route path="jobs" element={<JobsPage />} />
              <Route path="logs" element={<LogsPage />} />
              <Route path="dashboard" element={<DashboardPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/upload" replace />} />
          </Routes>
        </BrowserRouter>
      </UserProvider>
    </MsalProvider>
  );
}
