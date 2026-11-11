"use client";
import { useEffect } from "react";

export function LandingVisit() {
  useEffect(() => {
    const id = crypto.randomUUID();
    const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const send = (visible: boolean) => {
      void fetch(`${base}/api/admin/landing-visit`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, visible }), keepalive: true,
      }).catch(() => undefined);
    };
    send(!document.hidden);
    const timer = window.setInterval(() => { if (!document.hidden) send(true); }, 30000);
    const visibility = () => send(!document.hidden);
    document.addEventListener("visibilitychange", visibility);
    return () => { send(false); window.clearInterval(timer); document.removeEventListener("visibilitychange", visibility); };
  }, []);
  return null;
}
