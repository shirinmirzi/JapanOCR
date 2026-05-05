/**
 * Japan OCR Tool - Root Application Component
 *
 * Composes the top-level provider tree and declares all client-side routes
 * for the application.
 *
 * Key Features:
 * - Routing: Defines all page routes via React Router v6
 * - Auth Guard: Wraps protected routes with PrivateRoute
 * - Providers: Injects MSAL, UserContext, LangContext, and ModuleContext at the root
 *
 * Dependencies: React Router, @azure/msal-react, UserContext, ModuleContext
 * Author: SHIRIN MIRZI M K
 */
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MsalProvider } from '@azure/msal-react';
import { msalInstance } from './msalConfig';
import { UserProvider } from './context/UserContext';
import { ModuleProvider } from './context/ModuleContext';
import { LangProvider } from './context/LangContext';
import { ActiveJobProvider } from './context/ActiveJobContext';
import PrivateRoute from './components/PrivateRoute';
import MainLayout from './layouts/MainLayout';
import LoginPage from './pages/LoginPage';
import InvoiceUploadPage from './pages/InvoiceUploadPage';
import LogsPage from './pages/LogsPage';
import DashboardPage from './pages/DashboardPage';
import ConfigPage from './pages/ConfigPage';

export default function App() {
  return (
    <MsalProvider instance={msalInstance}>
      <UserProvider>
        <LangProvider>
        <ActiveJobProvider>
        <ModuleProvider>
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
              <Route path="logs" element={<LogsPage />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="config" element={<ConfigPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/upload" replace />} />
          </Routes>
        </BrowserRouter>
        </ModuleProvider>
        </ActiveJobProvider>
        </LangProvider>
      </UserProvider>
    </MsalProvider>
  );
}
