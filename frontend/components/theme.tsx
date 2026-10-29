"use client";
/* Modo claro/oscuro con persistencia local. */
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("licitaia-theme", next ? "dark" : "light");
    } catch {}
  }

  return (
    <button
      onClick={toggle}
      aria-label="Cambiar tema"
      className="border-base text-muted hover:text-teal inline-flex h-8 w-8 items-center justify-center rounded-lg border transition"
    >
      {dark ? "☀" : "☾"}
    </button>
  );
}

export function ThemeInitScript() {
  const code = `try{const t=localStorage.getItem('licitaia-theme');if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme: dark)').matches)){document.documentElement.classList.add('dark')}}catch(e){}`;
  return <script dangerouslySetInnerHTML={{ __html: code }} />;
}
