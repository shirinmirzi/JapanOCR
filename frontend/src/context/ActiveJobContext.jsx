/**
 * Japan OCR Tool - Active Job Context
 *
 * Provides a single source of truth for the active bulk-upload job. Polls
 * the backend for job status while a job is running and exposes job state
 * to all pages so it persists across route navigation.
 *
 * Key Features:
 * - Shared State: Single job state accessible by Upload and Logs pages
 * - Navigation Persistence: Context lives at App level so it never unmounts
 * - Auto Polling: Polls the backend every 1.5 s while the job is active
 * - localStorage Sync: Stores active job ID so page refreshes restore state
 *
 * Dependencies: services/api
 * Author: SHIRIN MIRZI M K
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { getBulkJob } from '../services/api';

const TERMINAL_STATUSES = new Set(['done', 'failed', 'cancelled', 'partial', 'interrupted']);
const POLL_INTERVAL_MS = 1500;
const LS_JOB_KEY = 'bulk_job_id';
const LS_MODE_KEY = 'upload_mode';

const ActiveJobContext = createContext(null);

/**
 * Wraps the application and provides a persistent active-job state shared
 * by all child pages. Automatically polls the backend while a job is
 * active and stops when the job reaches a terminal status.
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children
 * @returns {JSX.Element}
 */
export function ActiveJobProvider({ children }) {
  const [jobId, setJobIdState] = useState(() => localStorage.getItem(LS_JOB_KEY) || null);
  const [job, setJob] = useState(null);
  const pollRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  /**
   * Sets the active job ID, persisting it to localStorage so the state
   * survives page refreshes.
   */
  const setJobId = useCallback((id) => {
    if (id) {
      localStorage.setItem(LS_JOB_KEY, id);
      localStorage.setItem(LS_MODE_KEY, 'bulk');
    } else {
      localStorage.removeItem(LS_JOB_KEY);
    }
    setJobIdState(id);
  }, []);

  /**
   * Resets all active-job state and clears localStorage keys so the Upload
   * page returns to its initial empty state.
   */
  const clearJob = useCallback(() => {
    stopPolling();
    localStorage.removeItem(LS_JOB_KEY);
    localStorage.removeItem(LS_MODE_KEY);
    setJobIdState(null);
    setJob(null);
  }, [stopPolling]);

  // Start (or restart) polling whenever the active job ID changes.
  useEffect(() => {
    stopPolling();

    if (!jobId) {
      setJob(null);
      return;
    }

    let mounted = true;

    const poll = async () => {
      try {
        const data = await getBulkJob(jobId);
        if (!mounted) return;
        setJob(data);
        if (TERMINAL_STATUSES.has(data.status)) {
          stopPolling();
        }
      } catch {
        // Keep last known job state on transient network errors so the UI
        // does not flicker or lose information between retries.
        if (!mounted) return;
      }
    };

    poll();
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      mounted = false;
      stopPolling();
    };
  }, [jobId, stopPolling]);

  // True whenever a job exists and has not yet reached a terminal state.
  const isActive = !!job && !TERMINAL_STATUSES.has(job.status);

  // Memoize the context value so consumers only re-render when the data
  // they use actually changes, not on every provider render cycle.
  const value = useMemo(
    () => ({ jobId, job, setJob, setJobId, clearJob, isActive }),
    [jobId, job, setJob, setJobId, clearJob, isActive]
  );

  return (
    <ActiveJobContext.Provider value={value}>
      {children}
    </ActiveJobContext.Provider>
  );
}

/**
 * Consumes ActiveJobContext; throws if called outside an ActiveJobProvider.
 *
 * @returns {{ jobId: string|null, job: Object|null, setJob: Function,
 *             setJobId: Function, clearJob: Function, isActive: boolean }}
 */
export function useActiveJob() {
  const ctx = useContext(ActiveJobContext);
  if (!ctx) throw new Error('useActiveJob must be used within an ActiveJobProvider');
  return ctx;
}
