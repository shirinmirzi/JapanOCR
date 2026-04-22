import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useMsal } from '@azure/msal-react';
import { useUser } from '../context/UserContext';
import { clearDevLogin, isDevLogin } from '../services/api';
import { t, setLang, getLang, availableLangs } from '../i18n';

const HEADER_BG = '#002F45';
const ACTIVE_COLOR = '#00A9CE';

export default function Header() {
  const { instance } = useMsal();
  const { user = null } = useUser() || {};
  const navigate = useNavigate();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [lang, setLangState] = useState(getLang());

  const handleLangChange = (l) => {
    setLang(l);
    setLangState(l);
    window.location.reload();
  };

  const handleSignOut = () => {
    if (isDevLogin()) {
      clearDevLogin();
      navigate('/login', { replace: true });
      return;
    }

    instance.logoutRedirect({ postLogoutRedirectUri: '/login' });
  };

  const navItems = [
    { to: '/upload', label: t('nav_upload') },
    { to: '/logs', label: t('nav_logs') },
    { to: '/dashboard', label: t('nav_dashboard') },
  ];

  return (
    <header style={{ backgroundColor: HEADER_BG }} className="text-white shadow-md">
      <div className="w-full px-4 sm:px-6 md:px-8 lg:px-12 xl:px-16 2xl:px-24 py-3 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <span className="text-xl font-bold tracking-wide">{t('app_title')}</span>
          <nav className="hidden md:flex gap-6">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors ${
                    isActive ? 'border-b-2' : 'text-gray-300 hover:text-white'
                  }`
                }
                style={({ isActive }) =>
                  isActive ? { color: ACTIVE_COLOR, borderColor: ACTIVE_COLOR } : {}
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-4">
          {/* Language switcher */}
          <div className="flex gap-1">
            {availableLangs.map((l) => (
              <button
                key={l}
                onClick={() => handleLangChange(l)}
                className={`text-xs px-2 py-1 rounded ${
                  lang === l ? 'bg-white text-gray-900' : 'text-gray-300 hover:text-white'
                }`}
              >
                {l.toUpperCase()}
              </button>
            ))}
          </div>

          {/* User avatar */}
          {user && (
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center gap-2 focus:outline-none"
              >
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
                  style={{ backgroundColor: ACTIVE_COLOR }}
                >
                  {user.initials || '?'}
                </div>
              </button>
              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-white text-gray-900 z-50">
                  <div className="px-4 py-3 border-b">
                    <p className="font-semibold text-sm">{user.name}</p>
                    <p className="text-xs text-gray-500 truncate">{user.email}</p>
                  </div>
                  <button
                    onClick={handleSignOut}
                    className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100"
                  >
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
