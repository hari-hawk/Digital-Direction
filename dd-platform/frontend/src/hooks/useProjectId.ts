"use client";
import { useState, useEffect } from "react";

const DEFAULT_PROJECT = "nss";
const STORAGE_KEY = "dd_active_project";

/**
 * Read the active project ID from localStorage AFTER mount.
 * Returns { projectId, ready } — pages should wait for ready=true before loading data.
 * This prevents the flash of default project data when switching projects.
 */
export function useProjectId(): string {
  const [projectId, setProjectId] = useState(DEFAULT_PROJECT);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      setProjectId(stored);
    }
  }, []);

  // Return default during SSR, actual value after mount
  return projectId;
}

/**
 * Enhanced hook that also returns readiness state.
 * Use this when you need to prevent loading data for the wrong project.
 */
export function useProjectIdWithReady(): { projectId: string; ready: boolean } {
  const [projectId, setProjectId] = useState(DEFAULT_PROJECT);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      setProjectId(stored);
    }
    setReady(true);
  }, []);

  return { projectId, ready };
}
