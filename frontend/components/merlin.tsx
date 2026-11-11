"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export function Merlin() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("Hola, soy Merlín. Te acompaño con MySECOP y contratación pública colombiana.");
  const [loading, setLoading] = useState(false);
  async function ask() {
    if (!message.trim() || loading) return;
    setLoading(true);
    try { const data = await api<{ answer: string }>("/api/merlin/ask", { method: "POST", body: JSON.stringify({ message }) }); setReply(data.answer); setMessage(""); }
    catch { setReply("No pude responder en este momento. Intenta nuevamente; seguimos centrados en MySECOP y licitaciones."); }
    finally { setLoading(false); }
  }
  return <>
    <button aria-label="Abrir Merlín" onClick={() => setOpen(true)} className="fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-teal text-xl font-bold text-slate-950 shadow-xl transition hover:scale-105">M</button>
    {open && <div className="fixed inset-0 z-[70] flex items-end justify-end bg-slate-950/30 p-4 sm:items-center sm:p-8" onClick={() => setOpen(false)}>
      <section role="dialog" aria-modal="true" aria-label="Merlín" onClick={e => e.stopPropagation()} className="surface-card w-full max-w-md overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between border-b border-base bg-teal/10 px-5 py-4"><div><h2 className="font-bold">Merlín</h2><p className="text-xs text-muted">Tu guía de MySECOP y licitaciones</p></div><button onClick={() => setOpen(false)} className="text-xl text-muted">×</button></div>
        <div className="max-h-[55vh] space-y-4 overflow-auto p-5"><p className="rounded-xl bg-teal/10 p-3 text-sm leading-relaxed">{reply}</p><p className="text-[11px] text-muted">Respondo únicamente sobre MySECOP y contratación pública. Verifica siempre la fuente oficial de SECOP.</p></div>
        <div className="flex gap-2 border-t border-base p-4"><input value={message} onChange={e => setMessage(e.target.value)} onKeyDown={e => e.key === "Enter" && ask()} placeholder="Escribe tu pregunta…" className="min-w-0 flex-1 rounded-xl border border-base bg-transparent px-3 py-2 text-sm" /><button onClick={ask} disabled={loading || !message.trim()} className="rounded-xl bg-teal px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50">Enviar</button></div>
      </section>
    </div>}
  </>;
}
