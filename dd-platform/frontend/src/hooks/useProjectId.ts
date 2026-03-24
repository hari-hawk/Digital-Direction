"use client";
import { useState, useEffect } from "react";

const DEFAULT_PROJECT = "nss";
const STORAGE_KEY = "dd_active_project";

/**
 * Read the active project ID from localStorage AFTER mount.
 * Always returns DEFAULT_PROJECT during SSR and first render to prevent hydration mismatch.
 */
export function useProjectId(): string {
  const [projectId, setProjectId] = useState(DEFAULT_PROJECT);

  useEffect(() => {
    // Only read localStorage after mount (client-only)
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && stored !== DEFAULT_PROJECT) {
      setProjectId(stored);
    }
  }, []);

  return projectId;
}
