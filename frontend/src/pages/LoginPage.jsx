/**
 * Japan OCR Tool - Login Page
 *
 * Entry point for unauthenticated users. Initiates Microsoft Entra ID
 * (MSAL) login redirect flow and optionally exposes a developer bypass
 * login when running in dev mode or when VITE_ENABLE_DEV_LOGIN is set.
 *
 * Key Features:
 * - MSAL Login: Redirects to Entra ID via loginRedirect on button click
 * - Auto Redirect: Immediately navigates to /upload if already authenticated
 * - Dev Mode: Reveals a Dev Login button when running locally
 *
 * Dependencies: @azure/msal-react, React Router, msalConfig, services/api, i18n
 * Author: SHIRIN MIRZI M K
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIsAuthenticated } from '@azure/msal-react';
import { useMsal } from '@azure/msal-react';
import { loginRequest } from '../msalConfig';
import { enableDevLogin, isDevLogin } from '../services/api';
import { t } from '../i18n';
import { useLang } from '../context/LangContext';

/**
 * Renders the Microsoft Entra ID login page with an optional dev-login bypass.
 *
 * @returns {JSX.Element} Full-page login screen with sign-in button
 */
export default function LoginPage() {
  useLang();
  const isAuthenticated = useIsAuthenticated();
  const navigate = useNavigate();
  const { instance } = useMsal();
  const showDevLogin = import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEV_LOGIN === 'true';
  const [showDeveloperOptions, setShowDeveloperOptions] = useState(false);

  useEffect(() => {
    if (isAuthenticated || isDevLogin()) {
      navigate('/upload', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleLogin = () => {
    instance.loginRedirect(loginRequest);
  };

  const handleDevLogin = () => {
    enableDevLogin();
    navigate('/upload', { replace: true });
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4" style={{ backgroundColor: '#003b63' }}>
      <div className="w-full max-w-xl text-center text-white">
        <div className="mb-5">
          <div className="w-16 h-16 rounded-full mx-auto flex items-center justify-center bg-white text-3xl font-bold text-slate-900 shadow-md">
            J
          </div>
        </div>

        <h1 className="text-4xl font-bold mb-2">{t('login_title')}</h1>
        <p className="text-white/90 mb-8 text-lg">Sign in to continue</p>

        <div className="max-w-md mx-auto rounded-2xl shadow-2xl px-5 py-6" style={{ backgroundColor: 'rgba(255,255,255,0.12)' }}>
          <h2 className="text-2xl font-bold mb-4">Corporate Sign-In</h2>

          <button
            onClick={handleLogin}
            className="w-full py-3 px-6 rounded-lg bg-white text-slate-700 font-semibold text-base transition-opacity hover:opacity-95 shadow"
          >
            🪟 {t('login_btn')} (Entra ID)
          </button>

          <p className="text-xs text-white/80 mt-3 leading-5">
            Uses your corporate Microsoft account to access the application securely.
          </p>
        </div>

        {showDevLogin && (
          <div className="mt-4">
            <button
              onClick={() => setShowDeveloperOptions((v) => !v)}
              className="text-sm underline underline-offset-4 text-white/95 hover:text-white"
            >
              Developer Mode
            </button>

            {showDeveloperOptions && (
              <div className="mt-3 max-w-md mx-auto">
                <button
                  onClick={handleDevLogin}
                  className="w-full py-3 px-6 rounded-lg border border-white/40 bg-transparent text-white font-semibold text-base transition-colors hover:bg-white/10"
                >
                  Dev Login
                </button>
              </div>
            )}
          </div>
        )}

        <p className="text-xs text-white/80 mt-8">© 2026 Internal use only.</p>
      </div>
    </div>
  );
}
