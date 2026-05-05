/**
 * Japan OCR Tool - Job Context
 *
 * Single source of truth for active processing job state, shared by the
 * Upload and Logs pages.  Keeps polling alive at the root level so that
 * navigating between pages never resets or pauses the job status feed.
 *
 * Key Features:
 * - Bulk Job Polling: Polls getBulkJob every 1.2 s while a job ID is stored;
 *   continues across route changes because the provider lives at the app root
 * - Single Upload Flag: Persists a "single upload in progress" marker so the
 *   Upload page keeps showing its processing indicator after navigation
 * - localStorage Persistence: Survives soft page reloads for both flags
 *
 * Dependencies: services/api
 * Author: SHIRIN MIRZI M K
 */
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
} from 'react';
import { getBulkJob } from '../services/api';

const TERMINAL_STATUSES = new Set([
  'done',
  'failed',
  'cancelled',
  'partial',
  'interrupted',
]);

const POLL_INTERVAL_MS = 1200;

const JobContext = createContext(null);

/**
 * Provides shared active-job state to all descendant components.
 * Mount once at the application root so that polling survives navigation.
 *
 * @param {Object}           props
 * @param {React.ReactNode}  props.children
 */
export function JobProvider({ children }) {
  // ── Bulk job ────────────────────────────────────────────────────────────────
  const [bulkJobId, setBulkJobId] = useState(
    () => localStorage.getItem('bulk_job_id') || null,
  );
  const [bulkJob, setBulkJob] = useState(null);
  const pollRef = useRef(null);

  const stopBulkPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollBulkJob = useCallback(
    async (id) => {
      try {
        const data = await getBulkJob(id);
        setBulkJob(data);
        if (TERMINAL_STATUSES.has(data.status)) {
          stopBulkPolling();
        }
      } catch {
        // Keep showing last known state; don't clear job on transient errors
      }
    },
    [stopBulkPolling],
  );

  // Start / restart polling whenever bulkJobId changes
  useEffect(() => {
    if (!bulkJobId) {
      stopBulkPolling();
      setBulkJob(null);
      return;
    }
    // Fetch immediately so pages see data on first render, then clear any
    // existing interval before creating a new one (handles the case where
    // bulkJobId changes to a new value while a previous interval is still running).
    pollBulkJob(bulkJobId);
    stopBulkPolling();
    pollRef.current = setInterval(() => pollBulkJob(bulkJobId), POLL_INTERVAL_MS);
    return stopBulkPolling;
  }, [bulkJobId, pollBulkJob, stopBulkPolling]);

  /** Call after a new bulk job has been created on the backend. */
  const startBulkJob = useCallback((jobId) => {
    localStorage.setItem('bulk_job_id', jobId);
    localStorage.setItem('upload_mode', 'bulk');
    setBulkJobId(jobId);
  }, []);

  /**
   * Optimistically update the in-context job (e.g. after cancel).
   * @param {Function|Object} updater - functional updater or replacement object
   */
  const updateBulkJob = useCallback((updater) => {
    setBulkJob((prev) =>
      typeof updater === 'function' ? updater(prev) : updater,
    );
  }, []);

  /** Reset all bulk-job state and clear localStorage. */
  const resetBulkJob = useCallback(() => {
    stopBulkPolling();
    localStorage.removeItem('bulk_job_id');
    localStorage.removeItem('upload_mode');
    setBulkJobId(null);
    setBulkJob(null);
  }, [stopBulkPolling]);

  // True while a bulk job is queued or running (optimistically true before the
  // first poll if bulkJobId is set but bulkJob hasn't loaded yet).
  const isBulkJobActive = bulkJob
    ? !TERMINAL_STATUSES.has(bulkJob.status)
    : !!bulkJobId;

  // ── Single upload ────────────────────────────────────────────────────────────
  const [singleUploading, setSingleUploading] = useState(
    () => localStorage.getItem('single_upload_in_progress') === 'true',
  );

  /** Call when a single-invoice upload request is about to be sent. */
  const startSingleUpload = useCallback((filename) => {
    if (filename) localStorage.setItem('single_upload_filename', filename);
    localStorage.setItem('single_upload_in_progress', 'true');
    setSingleUploading(true);
  }, []);

  /** Call when a single-invoice upload completes or fails (success or error). */
  const endSingleUpload = useCallback(() => {
    localStorage.removeItem('single_upload_in_progress');
    localStorage.removeItem('single_upload_filename');
    setSingleUploading(false);
  }, []);

  // ── Context value ────────────────────────────────────────────────────────────
  return (
    <JobContext.Provider
      value={{
        // Bulk job
        bulkJobId,
        bulkJob,
        isBulkJobActive,
        startBulkJob,
        updateBulkJob,
        resetBulkJob,
        stopBulkPolling,
        // Single upload
        singleUploading,
        startSingleUpload,
        endSingleUpload,
      }}
    >
      {children}
    </JobContext.Provider>
  );
}

/**
 * Returns the active job context.  Must be called inside a <JobProvider>.
 *
 * @returns {Object} Job context with bulk-job and single-upload state/actions
 */
export function useJob() {
  const ctx = useContext(JobContext);
  if (!ctx) throw new Error('useJob must be used within a JobProvider');
  return ctx;
}
