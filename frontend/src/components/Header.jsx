import React, { useEffect, useRef, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useMsal } from '@azure/msal-react';
import { useUser } from '../context/UserContext';
import { useModule } from '../context/ModuleContext';
import { clearDevLogin, isDevLogin } from '../services/api';
import { t, setLang, getLang, availableLangs } from '../i18n';

const HEADER_BG = '#002F45';
const NAV_BG = '#00253A';
const ACTIVE_COLOR = '#00A9CE';

const MODULES = ['invoice', 'fax'];

const MODULE_ICONS = {
  invoice: (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  ),
  fax: (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
    </svg>
  ),
};

export default function Header() {
  const { instance } = useMsal();
  const { user = null } = useUser() || {};
  const { module, setModule } = useModule();
  const navigate = useNavigate();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [lang, setLangState] = useState(getLang());
  const dropdownRef = useRef(null);

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

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const navItems = [
    { to: '/upload', label: t('nav_upload') },
    { to: '/logs', label: t('nav_logs') },
    { to: '/jobs', label: t('nav_jobs') },
    { to: '/dashboard', label: t('nav_dashboard') },
    { to: '/config', label: t('nav_config') },
  ];

  return (
    <header className="text-white shadow-lg" style={{ backgroundColor: HEADER_BG }}>
      {/* Top bar: logo + module toggle + right controls */}
      <div className="w-full px-4 sm:px-6 lg:px-12 xl:px-16 2xl:px-24 py-3 flex items-center justify-between">
        {/* Left: Logo + module toggle */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div
              className="w-7 h-7 rounded flex items-center justify-center text-xs font-bold"
              style={{ backgroundColor: ACTIVE_COLOR }}
            >
              OCR
            </div>
            <span className="text-lg font-bold tracking-wide">{t('app_title')}</span>
          </div>

          {/* Divider */}
          <div className="h-5 w-px bg-white/20" />

          {/* Module toggle – positioned next to the branding */}
          <div className="flex items-center gap-1">
            {MODULES.map((m) => (
              <button
                key={m}
                onClick={() => setModule(m)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wide transition-all ${
                  module === m
                    ? 'text-white'
                    : 'text-white/50 hover:text-white/80 hover:bg-white/10'
                }`}
                style={module === m ? { backgroundColor: ACTIVE_COLOR } : undefined}
              >
                {MODULE_ICONS[m]}
                {t(`logs_module_${m}`)}
              </button>
            ))}
          </div>
        </div>

        {/* Right side: lang + user */}
        <div className="flex items-center gap-3">
          {/* Language switcher */}
          <div className="flex gap-0.5 bg-white/10 rounded-md p-0.5">
            {availableLangs.map((l) => (
              <button
                key={l}
                onClick={() => handleLangChange(l)}
                className={`text-xs px-2.5 py-1 rounded transition-colors font-medium ${
                  lang === l
                    ? 'bg-white text-gray-900'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                {l.toUpperCase()}
              </button>
            ))}
          </div>

          {/* User avatar */}
          {user && (
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center gap-2 focus:outline-none group"
              >
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ring-2 ring-white/20 group-hover:ring-white/40 transition-all"
                  style={{ backgroundColor: ACTIVE_COLOR }}
                >
                  {user.initials || '?'}
                </div>
                {user.name && (
                  <span className="hidden lg:block text-sm text-white/80 group-hover:text-white transition-colors">
                    {user.name.split(' ')[0]}
                  </span>
                )}
              </button>
              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 rounded-lg shadow-xl bg-white text-gray-900 z-50 border border-gray-100 overflow-hidden">
                  <div className="px-4 py-3 bg-gray-50 border-b border-gray-100">
                    <p className="font-semibold text-sm text-gray-900">{user.name}</p>
                    <p className="text-xs text-gray-500 truncate mt-0.5">{user.email}</p>
                  </div>
                  <button
                    onClick={handleSignOut}
                    className="w-full text-left px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2 transition-colors"
                  >
                    <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Bottom bar: navigation tabs directly under the module selector */}
      <div style={{ backgroundColor: NAV_BG }} className="border-t border-white/10">
        <div className="w-full px-4 sm:px-6 lg:px-12 xl:px-16 2xl:px-24 flex items-center justify-start">
          {/* Navigation links */}
          <nav className="hidden md:flex items-center">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `px-3 py-2.5 text-xs font-medium tracking-wide transition-all border-b-2 ${
                    isActive
                      ? 'text-white'
                      : 'text-white/60 border-transparent hover:text-white hover:border-white/30'
                  }`
                }
                style={({ isActive }) => isActive ? { borderColor: ACTIVE_COLOR } : undefined}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </div>
    </header>
  );
}
