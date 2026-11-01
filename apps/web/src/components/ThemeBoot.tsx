"use client";
import { useEffect } from "react";

export function applyTheme(theme: string | null) {
  const dark = theme === "dark" || (theme !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

/** Runs in an effect rather than an inline script, so the strict CSP needs no exception. */
export function ThemeBoot() {
  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = localStorage.getItem("rsv-theme");
    } catch {}
    applyTheme(saved);
  }, []);
  return null;
}
