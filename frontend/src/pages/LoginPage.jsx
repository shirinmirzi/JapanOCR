import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIsAuthenticated } from '@azure/msal-react';
import { useMsal } from '@azure/msal-react';
import { loginRequest } from '../msalConfig';
import { t } from '../i18n';

export default function LoginPage() {
  const isAuthenticated = useIsAuthenticated();
  const navigate = useNavigate();
  const { instance } = useMsal();

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/upload', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleLogin = () => {
    instance.loginRedirect(loginRequest);
  };

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center"
      style={{ background: 'linear-gradient(135deg, #00263A 0%, #009DD0 100%)' }}
    >
      <div className="bg-white rounded-2xl shadow-2xl p-10 w-full max-w-md text-center">
        {/* Logo placeholder */}
        <div className="mb-6">
          <div
            className="w-16 h-16 rounded-full mx-auto flex items-center justify-center text-white text-2xl font-bold"
            style={{ backgroundColor: '#002F45' }}
          >
            IP
          </div>
        </div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">{t('login_title')}</h1>
        <p className="text-gray-500 mb-8">OCR-powered invoice data extraction</p>
        <button
          onClick={handleLogin}
          className="w-full py-3 px-6 rounded-lg text-white font-semibold text-base transition-opacity hover:opacity-90"
          style={{ backgroundColor: '#009DD0' }}
        >
          {t('login_btn')}
        </button>
      </div>
    </div>
  );
}
