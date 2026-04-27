/**
 * Japan OCR Tool - Microsoft Authentication Library (MSAL) Configuration
 *
 * Initialises and exports the MSAL PublicClientApplication instance and
 * the login request scopes used throughout the application.
 *
 * Key Features:
 * - MSAL Config: Builds auth, cache, and logger settings from env variables
 * - Login Request: Defines OAuth2 scopes required for API access
 * - Instance Export: Provides a single shared MSAL instance for the app
 *
 * Dependencies: @azure/msal-browser
 * Author: SHIRIN MIRZI M K
 */
import { PublicClientApplication, LogLevel } from '@azure/msal-browser';

const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID || '';
const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID || '';

export const msalConfig = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return;
        if (level === LogLevel.Error) console.error(message);
      },
    },
  },
};

export const loginRequest = {
  scopes: ['openid', 'profile', 'User.Read'],
};

export const msalInstance = new PublicClientApplication(msalConfig);
