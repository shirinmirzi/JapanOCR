/**
 * Japan OCR Tool - Application Entry Point
 *
 * Bootstraps the React application by mounting the root component into the DOM.
 *
 * Key Features:
 * - Bootstrap: Mounts the React root with StrictMode enabled
 * - StrictMode: Highlights potential issues during development
 *
 * Dependencies: React, ReactDOM
 * Author: SHIRIN MIRZI M K
 */
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
