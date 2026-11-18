"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { Button, Field, Input, Select, Textarea } from "@/components/ui";

export function ContactForm() {
  const [form, setForm] = useState({ nombre: "", email: "", telefono: "", motivo: "", mensaje: "" });
  const [estado, setEstado] = useState<"idle" | "enviando" | "enviado" | "error">("idle");
  const [detalle, setDetalle] = useState("");
  const update = (key: keyof typeof form, value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  async function enviar(event: FormEvent) {
    event.preventDefault();
    setEstado("enviando");
    setDetalle("");
    try {
      const result = await api<{ correo_entregado: boolean; nota?: string | null }>("/api/contact", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setEstado("enviado");
      setDetalle(result.correo_entregado ? "Recibimos tu mensaje. Te responderemos pronto." : (result.nota || "Recibimos tu mensaje y lo registramos correctamente."));
    } catch (error) {
      setEstado("error");
      setDetalle(error instanceof Error ? error.message : "No fue posible enviar el mensaje.");
    }
  }

  return <>
    {estado === "enviado" ? <div role="status" className="mt-6 rounded-xl border border-teal/40 bg-teal/10 p-5 text-sm text-teal">{detalle}</div> : <form onSubmit={enviar} className="mt-6 grid gap-4 sm:grid-cols-2">
    <Field label="Nombres y apellidos"><Input required autoComplete="name" maxLength={120} minLength={2} value={form.nombre} onChange={(e) => update("nombre", e.target.value)} /></Field>
    <Field label="Correo electrónico"><Input required autoComplete="email" type="email" value={form.email} onChange={(e) => update("email", e.target.value)} /></Field>
    <Field label="Teléfono"><Input required autoComplete="tel" maxLength={40} type="tel" inputMode="tel" value={form.telefono} onChange={(e) => update("telefono", e.target.value)} /></Field>
    <Field label="Motivo de consulta"><Select value={form.motivo} onChange={(e) => update("motivo", e.target.value)}><option value="">Selecciona una opción</option><option>Conocer MySECOP</option><option>Licencia corporativa</option><option>Soporte o reporte de error</option><option>Sugerencia de mejora</option><option>Otro</option></Select></Field>
    <div className="sm:col-span-2"><Field label="Cuéntanos cómo podemos ayudarte"><Textarea required minLength={10} maxLength={4000} rows={4} value={form.mensaje} onChange={(e) => update("mensaje", e.target.value)} /></Field></div>
    {estado === "error" ? <p role="alert" className="text-xs text-red-500 sm:col-span-2">{detalle}</p> : null}
    <div className="sm:col-span-2"><Button type="submit" disabled={estado === "enviando"}>{estado === "enviando" ? "Enviando…" : "Enviar consulta"}</Button></div>
  </form>}
    <div className="mt-6 border-t border-base pt-5">
      <p className="text-muted mb-3 text-sm">¿Prefieres hablar por WhatsApp?</p>
      <a
        href="https://wa.me/573204930650?text=Hola%2C%20quiero%20conocer%20m%C3%A1s%20sobre%20MySECOP."
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center justify-center rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600"
      >
        Escribir por WhatsApp
      </a>
      <p className="text-muted mt-2 text-xs">+57 320 493 0650 · Se abre en una nueva pestaña.</p>
    </div>
  </>;
}
