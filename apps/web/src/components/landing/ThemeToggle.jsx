"use client";
import { useEffect, useState } from "react";
function ThemeToggle() {
  const [theme, setTheme] = useState("light");
  useEffect(() => {
    try {
      const stored = localStorage.getItem("geosar-landing-theme") === "dark" ? "dark" : "light";
      setTheme(stored);
      document.querySelector(".landing")?.classList.toggle("light", stored === "light");
    } catch { /* Storage may be disabled. */ }
  }, []);
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    const el = document.querySelector(".landing");
    el.classList.remove("light", "dark");
    el.classList.add(next);
    try {
      localStorage.setItem("geosar-landing-theme", next);
    } catch {
    }
  };
  const isDark = theme === "dark";
  return <button
    onClick={toggle}
    aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
    title={isDark ? "Light theme" : "Dark theme"}
    className="flex h-9 w-9 items-center justify-center rounded-md border border-line/15 bg-fg/5 text-muted transition hover:border-accent/40 hover:text-accent"
  >{isDark ? (
    // sun (switch to light)
    <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current" aria-hidden><path d="M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zm0-13a1 1 0 0 1 1 1v1a1 1 0 1 1-2 0V5a1 1 0 0 1 1-1zm0 15a1 1 0 0 1 1 1v1a1 1 0 1 1-2 0v-1a1 1 0 0 1 1-1zM4 11a1 1 0 0 1 1-1h1a1 1 0 1 1 0 2H5a1 1 0 0 1-1-1zm14 0a1 1 0 0 1 1-1h1a1 1 0 1 1 0 2h-1a1 1 0 0 1-1-1zM5.6 5.6a1 1 0 0 1 1.4 0l.7.7A1 1 0 1 1 6.3 7.7l-.7-.7a1 1 0 0 1 0-1.4zm10.6 10.6a1 1 0 0 1 1.4 0l.7.7a1 1 0 1 1-1.4 1.4l-.7-.7a1 1 0 0 1 0-1.4zm1.4-10.6a1 1 0 0 1 0 1.4l-.7.7a1 1 0 1 1-1.4-1.4l.7-.7a1 1 0 0 1 1.4 0zM6.3 16.3a1 1 0 0 1 0 1.4l-.7.7a1 1 0 1 1-1.4-1.4l.7-.7a1 1 0 0 1 1.4 0z" /></svg>
  ) : (
    // moon (switch to dark)
    <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current" aria-hidden><path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a7 7 0 1 0 9.8 9.8z" /></svg>
  )}</button>;
}
export {
  ThemeToggle
};
