"use client";
import { useEffect, useState } from "react";

// ─── Types ──────────────────────────────────────────────

export type ToastType = "success" | "info" | "warning" | "error";

export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number; // ms, default 5000
}

// ─── Global toast state (singleton) ─────────────────────

type ToastListener = (toasts: Toast[]) => void;

let _toasts: Toast[] = [];
let _listeners: ToastListener[] = [];
let _nextId = 0;

function _notify() {
  for (const fn of _listeners) {
    fn([..._toasts]);
  }
}

/** Show a toast notification. Can be called from anywhere (not just React). */
export function showToast(
  type: ToastType,
  title: string,
  message?: string,
  duration?: number,
) {
  const id = `toast-${++_nextId}-${Date.now()}`;
  const toast: Toast = { id, type, title, message, duration: duration ?? 5000 };
  _toasts = [..._toasts, toast];
  _notify();

  // Auto-dismiss
  const dur = toast.duration ?? 5000;
  if (dur > 0) {
    setTimeout(() => {
      dismissToast(id);
    }, dur);
  }
}

/** Dismiss a specific toast by ID. */
export function dismissToast(id: string) {
  _toasts = _toasts.filter((t) => t.id !== id);
  _notify();
}

/** Subscribe to toast changes. Returns unsubscribe function. */
function subscribe(fn: ToastListener): () => void {
  _listeners.push(fn);
  return () => {
    _listeners = _listeners.filter((l) => l !== fn);
  };
}

// ─── Convenience helpers ────────────────────────────────

export const toast = {
  success: (title: string, message?: string) => showToast("success", title, message),
  info: (title: string, message?: string) => showToast("info", title, message),
  warning: (title: string, message?: string) => showToast("warning", title, message),
  error: (title: string, message?: string) => showToast("error", title, message),
};

// ─── Styles ─────────────────────────────────────────────

const TYPE_STYLES: Record<ToastType, { bg: string; border: string; icon: string; text: string }> = {
  success: {
    bg: "bg-emerald-950/90",
    border: "border-emerald-500/30",
    icon: "text-emerald-400",
    text: "text-emerald-300",
  },
  info: {
    bg: "bg-blue-950/90",
    border: "border-blue-500/30",
    icon: "text-blue-400",
    text: "text-blue-300",
  },
  warning: {
    bg: "bg-amber-950/90",
    border: "border-amber-500/30",
    icon: "text-amber-400",
    text: "text-amber-300",
  },
  error: {
    bg: "bg-red-950/90",
    border: "border-red-500/30",
    icon: "text-red-400",
    text: "text-red-300",
  },
};

const TYPE_ICONS: Record<ToastType, string> = {
  success: "M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  info: "M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z",
  warning: "M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z",
  error: "M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
};

// ─── Component ──────────────────────────────────────────

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    return subscribe(setToasts);
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((t) => {
        const style = TYPE_STYLES[t.type];
        const iconPath = TYPE_ICONS[t.type];
        return (
          <div
            key={t.id}
            className={`pointer-events-auto ${style.bg} ${style.border} border rounded-lg p-3 shadow-lg backdrop-blur-sm animate-in slide-in-from-right-full fade-in duration-300`}
          >
            <div className="flex items-start gap-2.5">
              {/* Icon */}
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className={`w-5 h-5 shrink-0 mt-0.5 ${style.icon}`}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d={iconPath} />
              </svg>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${style.text}`}>{t.title}</p>
                {t.message && (
                  <p className="text-xs text-zinc-400 mt-0.5 line-clamp-2">{t.message}</p>
                )}
              </div>

              {/* Dismiss */}
              <button
                onClick={() => dismissToast(t.id)}
                className="shrink-0 text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                  <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                </svg>
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
