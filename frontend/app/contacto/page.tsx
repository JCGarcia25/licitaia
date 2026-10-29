"use client";
/* Página de contacto funcional (Fase 5): guarda el mensaje en la base y notifica por SMTP si está configurado. */
import { FormEvent, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button, Field, Input, Textarea } from "@/components/ui";

export default function Contacto() {
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [estado, setEstado] = useState<"idle" | "enviando" | "enviado" | "error">("idle");
  const [detalle, setDetalle] = useState("");

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEstado("enviando");
    setDetalle("");
    try {
      const r = await api<{ recibido: boolean; correo_entregado: boolean; nota: string | null }>("/api/contact", {
        method: "POST",
        body: JSON.stringify({ nombre, email, mensaje }),
      });
      setEstado("enviado");
      setDetalle(r.correo_entregado ? "Hemos recibido tu mensaje y te responderemos pronto." : (r.nota || "Mensaje registrado."));
    } catch (err) {
      setEstado("error");
      setDetalle(err instanceof Error ? err.message : "No fue posible enviar el mensaje");
    }
  }

  return (
    <div className="hero-grid min-h-screen px-5 py-16">
      <div className="mx-auto max-w-xl">
        <Link href="/" className="mb-8 flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-900 font-bold text-white dark:bg-teal dark:text-slate-950">L</span>
          <span className="text-lg font-bold">LicitaIA</span>
        </Link>
        <div className="surface-card shadow-card p-8">
          <h1 className="text-xl font-bold tracking-tight">Contáctanos</h1>
          <p className="text-muted mt-1 text-sm">Cuéntanos sobre tu empresa y te mostramos las oportunidades que encajan.</p>
          {estado === "enviado" ? (
            <div className="mt-6 rounded-lg border border-teal/40 bg-teal-50 px-4 py-3 text-sm text-teal-800 dark:bg-teal-900/20 dark:text-teal-300">
              Mensaje enviado. {detalle}
            </div>
          ) : (
            <form onSubmit={enviar} className="mt-6 space-y-4">
              <Field label="Nombre"><Input required value={nombre} onChange={(e) => setNombre(e.target.value)} /></Field>
              <Field label="Correo"><Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
              <Field label="Mensaje"><Textarea rows={5} required minLength={10} value={mensaje} onChange={(e) => setMensaje(e.target.value)} /></Field>
              {estado === "error" ? <p className="text-xs text-red-600">{detalle}</p> : null}
              <Button type="submit" disabled={estado === "enviando"} className="w-full">
                {estado === "enviando" ? "Enviando…" : "Enviar mensaje"}
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
