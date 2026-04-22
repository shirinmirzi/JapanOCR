import axios from 'axios';
import { msalInstance, loginRequest } from '../msalConfig';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
const DEV_LOGIN_KEY = 'invoice_processor_dev_login';

export function isDevLogin() {
  return localStorage.getItem(DEV_LOGIN_KEY) === 'true';
}

export function enableDevLogin() {
  localStorage.setItem(DEV_LOGIN_KEY, 'true');
}

export function clearDevLogin() {
  localStorage.removeItem(DEV_LOGIN_KEY);
}

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

async function apiGet(path, params = {}) {
  const headers = await getAuthHeader();
  const response = await axios.get(`${BASE_URL}${path}`, { params, headers });
  return response.data;
}

async function apiPost(path, data, isFormData = false) {
  const headers = await getAuthHeader();
  if (!isFormData) headers['Content-Type'] = 'application/json';
  const response = await axios.post(`${BASE_URL}${path}`, data, { headers });
  return response.data;
}

async function apiDelete(path) {
  const headers = await getAuthHeader();
  const response = await axios.delete(`${BASE_URL}${path}`, { headers });
  return response.data;
}

// Auth
export async function checkAuth() {
  return apiGet('/auth/me');
}

export async function logout() {
  if (isDevLogin()) {
    clearDevLogin();
    window.location.assign('/login');
    return;
  }

  msalInstance.logoutRedirect({ postLogoutRedirectUri: '/login' });
}

// Invoice operations
export async function uploadInvoice(file, invoiceType = 'daily', userDate = null) {
  const headers = await getAuthHeader();
  const formData = new FormData();
  formData.append('file', file);
  formData.append('invoice_type', invoiceType);
  if (userDate) formData.append('user_date', userDate);
  const response = await axios.post(`${BASE_URL}/api/invoices/upload`, formData, { headers });
  return response.data;
}

export async function bulkUploadInvoices(files, invoiceType = 'daily', userDate = null) {
  const headers = await getAuthHeader();
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  formData.append('invoice_type', invoiceType);
  if (userDate) formData.append('user_date', userDate);
  const response = await axios.post(`${BASE_URL}/api/invoices/bulk-upload`, formData, { headers });
  return response.data;
}

export async function getBulkJob(jobId) {
  return apiGet(`/jobs/${jobId}`);
}

export async function cancelBulkJob(jobId) {
  return apiPost(`/jobs/${jobId}/cancel`);
}

export async function getInvoicesPaged(params = {}) {
  return apiGet('/api/invoices/paged', params);
}

export async function getInvoiceById(invoiceId) {
  return apiGet(`/api/invoices/${invoiceId}`);
}

export async function getInvoicesByJob(jobId) {
  return apiGet(`/api/invoices/job/${jobId}`);
}

export async function deleteInvoice(invoiceId) {
  return apiDelete(`/api/invoices/${invoiceId}`);
}

export async function getInvoiceDownloadUrl(invoiceId) {
  return apiGet(`/api/invoices/${invoiceId}/download`);
}

// Jobs
export async function getJobsPaged(params = {}) {
  return apiGet('/jobs/paged', params);
}

// Logs
export async function getLogsPaged(params = {}) {
  return apiGet('/logs/db/paged', params);
}

// Dashboard
export async function getDashboardSummary(params = {}) {
  return apiGet('/api/dashboard/summary', params);
}
