/**
 * Japan OCR Tool - API Service Layer
 *
 * Centralises all HTTP communication with the backend. Handles auth header
 * injection (MSAL silent token or dev-login bypass) and exposes typed
 * wrappers for every backend endpoint.
 *
 * Key Features:
 * - Auth Injection: Silently acquires MSAL tokens or uses dev-token header
 * - Dev Login: localStorage flag lets developers bypass Entra ID locally
 * - Typed Endpoints: Named exports for every backend route group
 *
 * Dependencies: axios, @azure/msal-browser (via msalConfig)
 * Author: SHIRIN MIRZI M K
 */
import axios from 'axios';
import { msalInstance, loginRequest } from '../msalConfig';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
const DEV_LOGIN_KEY = 'invoice_processor_dev_login';

/**
 * Returns true when the dev-login bypass flag is set in localStorage.
 *
 * @returns {boolean} Whether dev login is currently active
 */
export function isDevLogin() {
  return localStorage.getItem(DEV_LOGIN_KEY) === 'true';
}

/**
 * Activates the dev-login bypass by writing the flag to localStorage.
 *
 * @returns {void}
 */
export function enableDevLogin() {
  localStorage.setItem(DEV_LOGIN_KEY, 'true');
}

/**
 * Removes the dev-login bypass flag from localStorage.
 *
 * @returns {void}
 */
export function clearDevLogin() {
  localStorage.removeItem(DEV_LOGIN_KEY);
}

/**
 * Builds the Authorization header for the current session.
 * Uses a static dev-token when dev-login is active to avoid MSAL overhead.
 *
 * @returns {Promise<Object>} Header object with Authorization field, or {}
 */
async function getAuthHeader() {
  if (isDevLogin()) {
    return { Authorization: 'Bearer dev-token' };
  }

  const accounts = msalInstance.getAllAccounts();
  if (accounts.length === 0) return {};
  try {
    const response = await msalInstance.acquireTokenSilent({
      ...loginRequest,
      account: accounts[0],
    });
    return { Authorization: `Bearer ${response.accessToken}` };
  } catch {
    return {};
  }
}

/**
 * Performs an authenticated GET request and returns the response data.
 *
 * @param {string} path - API path (appended to BASE_URL)
 * @param {Object} params - URL query parameters
 * @returns {Promise<Object>} Parsed response body
 */
async function apiGet(path, params = {}) {
  const headers = await getAuthHeader();
  const response = await axios.get(`${BASE_URL}${path}`, { params, headers });
  return response.data;
}

/**
 * Performs an authenticated POST request and returns the response data.
 *
 * @param {string} path - API path (appended to BASE_URL)
 * @param {Object|FormData} data - Request body
 * @param {boolean} isFormData - When true, skips setting Content-Type so the
 *   browser can set the multipart boundary automatically
 * @returns {Promise<Object>} Parsed response body
 */
async function apiPost(path, data, isFormData = false) {
  const headers = await getAuthHeader();
  if (!isFormData) headers['Content-Type'] = 'application/json';
  const response = await axios.post(`${BASE_URL}${path}`, data, { headers });
  return response.data;
}

/**
 * Performs an authenticated DELETE request and returns the response data.
 *
 * @param {string} path - API path (appended to BASE_URL)
 * @returns {Promise<Object>} Parsed response body
 */
async function apiDelete(path) {
  const headers = await getAuthHeader();
  const response = await axios.delete(`${BASE_URL}${path}`, { headers });
  return response.data;
}

// Auth
/**
 * Fetches the currently authenticated user profile from the backend.
 *
 * @returns {Promise<Object>} User profile object (name, email, initials, etc.)
 */
export async function checkAuth() {
  return apiGet('/auth/me');
}

/**
 * Signs the user out. Clears dev-login flag or triggers MSAL redirect logout.
 *
 * @returns {Promise<void>}
 */
export async function logout() {
  if (isDevLogin()) {
    clearDevLogin();
    window.location.assign('/login');
    return;
  }

  msalInstance.logoutRedirect({ postLogoutRedirectUri: '/login' });
}

// Config / Master Data
/**
 * Uploads a master data file (Excel/CSV) for a given master type.
 *
 * @param {string} masterType - Master type identifier ('daily' or 'monthly')
 * @param {File} file - Excel or CSV file to upload
 * @returns {Promise<Object>} Upload result with inserted/skipped/invalid counts
 */
export async function uploadMasterData(masterType, file) {
  const headers = await getAuthHeader();
  const formData = new FormData();
  formData.append('master_type', masterType);
  formData.append('file', file);
  const response = await axios.post(`${BASE_URL}/api/config/master-upload`, formData, { headers });
  return response.data;
}

/**
 * Retrieves the current master data records for a given master type.
 *
 * @param {string} masterType - Master type identifier ('daily' or 'monthly')
 * @returns {Promise<Object>} Master data records from the backend
 */
export async function getMasterData(masterType) {
  return apiGet(`/api/config/master-data/${masterType}`);
}

// Invoice operations
/**
 * Uploads a single invoice PDF for OCR processing.
 *
 * @param {File} file - PDF invoice file
 * @param {string} invoiceType - Invoice type ('daily' or 'monthly')
 * @param {string|null} userDate - Optional override date (ISO string)
 * @returns {Promise<Object>} Processing result with extracted invoice data
 */
export async function uploadInvoice(file, invoiceType = 'daily', userDate = null) {
  const headers = await getAuthHeader();
  const formData = new FormData();
  formData.append('file', file);
  formData.append('invoice_type', invoiceType);
  if (userDate) formData.append('user_date', userDate);
  const response = await axios.post(`${BASE_URL}/api/invoices/upload`, formData, { headers });
  return response.data;
}

/**
 * Submits multiple invoice PDFs as a single bulk-processing job.
 *
 * @param {File[]} files - Array of PDF invoice files
 * @param {string} invoiceType - Invoice type ('daily' or 'monthly')
 * @param {string|null} userDate - Optional override date (ISO string)
 * @returns {Promise<Object>} Bulk job details including job ID
 */
export async function bulkUploadInvoices(files, invoiceType = 'daily', userDate = null) {
  const headers = await getAuthHeader();
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  formData.append('invoice_type', invoiceType);
  if (userDate) formData.append('user_date', userDate);
  const response = await axios.post(`${BASE_URL}/api/invoices/bulk-upload`, formData, { headers });
  return response.data;
}

/**
 * Polls the current status and progress of a bulk-upload job.
 *
 * @param {string} jobId - Unique identifier of the bulk job
 * @returns {Promise<Object>} Job status object with progress and item results
 */
export async function getBulkJob(jobId) {
  return apiGet(`/jobs/${jobId}`);
}

/**
 * Requests cancellation of an in-progress bulk-upload job.
 *
 * @param {string} jobId - Unique identifier of the bulk job to cancel
 * @returns {Promise<Object>} Cancellation acknowledgement from the backend
 */
export async function cancelBulkJob(jobId) {
  return apiPost(`/jobs/${jobId}/cancel`);
}

/**
 * Fetches a paginated list of invoices matching the given filter parameters.
 *
 * @param {Object} params - Query parameters (page, page_size, status, etc.)
 * @returns {Promise<Object>} Paginated invoices response with total count
 */
export async function getInvoicesPaged(params = {}) {
  return apiGet('/api/invoices/paged', params);
}

/**
 * Retrieves a single invoice record by its unique identifier.
 *
 * @param {string} invoiceId - Unique identifier of the invoice
 * @returns {Promise<Object>} Full invoice record including extracted fields
 */
export async function getInvoiceById(invoiceId) {
  return apiGet(`/api/invoices/${invoiceId}`);
}

/**
 * Fetches all invoices that belong to a specific bulk-upload job.
 *
 * @param {string} jobId - Unique identifier of the bulk job
 * @returns {Promise<Object[]>} Array of invoice records for the job
 */
export async function getInvoicesByJob(jobId) {
  return apiGet(`/api/invoices/job/${jobId}`);
}

/**
 * Deletes an invoice record from the backend by its unique identifier.
 *
 * @param {string} invoiceId - Unique identifier of the invoice to delete
 * @returns {Promise<Object>} Deletion acknowledgement from the backend
 */
export async function deleteInvoice(invoiceId) {
  return apiDelete(`/api/invoices/${invoiceId}`);
}

/**
 * Returns a signed or proxied download URL for the original invoice file.
 *
 * @param {string} invoiceId - Unique identifier of the invoice
 * @returns {Promise<Object>} Object containing the download URL
 */
export async function getInvoiceDownloadUrl(invoiceId) {
  return apiGet(`/api/invoices/${invoiceId}/download`);
}

// Jobs
/**
 * Fetches a paginated list of bulk-upload jobs.
 *
 * @param {Object} params - Query parameters (page, page_size, status, etc.)
 * @returns {Promise<Object>} Paginated jobs response with total count
 */
export async function getJobsPaged(params = {}) {
  return apiGet('/jobs/paged', params);
}

// Logs
/**
 * Fetches a paginated list of activity log entries.
 *
 * @param {Object} params - Query parameters (page, page_size, status, since…)
 * @returns {Promise<Object>} Paginated logs response with total count
 */
export async function getLogsPaged(params = {}) {
  return apiGet('/logs/db/paged', params);
}

// Dashboard
/**
 * Retrieves aggregated KPI and recent-activity data for the dashboard.
 *
 * @param {Object} params - Query parameters (since, jobs_limit, invoices_limit…)
 * @returns {Promise<Object>} Summary object with kpis and recent activity
 */
export async function getDashboardSummary(params = {}) {
  return apiGet('/api/dashboard/summary', params);
}
