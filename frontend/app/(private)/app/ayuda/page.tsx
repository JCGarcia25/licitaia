"use client";
import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { Button, Card, CardHeader, Field, Select, Textarea } from "@/components/ui";

export default function AyudaPage() {
  const [tipo, setTipo] = useState("sugerencia");
  const [mensaje, setMensaje] = useState("");
  const [estado, setEstado] = useState<"idle" | "enviando" | "enviado" | "error">("idle");
  const [detalle, setDetalle] = useState("");

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setEstado("enviando"); setDetalle("");
    try {
      const prefijo = tipo === "error" ? "Reporte de error" : "Sugerencia de nueva funcionalidad";
      const respuesta = await api<{ nota?: string; correo_entregado?: boolean }>("/api/contact", {
        method: "POST",
        body: JSON.stringify({ nombre: "Usuario MySECOP", email: "soporte@mysecop.co", mensaje: `[${prefijo}]\n\n${mensaje}` }),
      });
      setEstado("enviado");
      setDetalle(respuesta.nota || "Recibimos tu mensaje y lo revisaremos con nuestro equipo.");
    } catch (error) { setEstado("error"); setDetalle(error instanceof Error ? error.message : "No fue posible enviar el mensaje."); }
  }

  return <div className="mx-auto max-w-3xl space-y-6">
    <div><h1 className="text-2xl font-bold tracking-tight">Ayúdanos a mejorar MySECOP</h1><p className="text-muted mt-1">MySECOP evoluciona constantemente para ser tu aliado perfecto y ayudarte a ganar muchos procesos.</p></div>
    <Card><CardHeader title="Sugerencias y reportes" subtitle="Tu experiencia nos ayuda a construir una herramienta más útil. Cuenta con todo nuestro acompañamiento." />
      {estado === "enviado" ? <div className="m-5 rounded-xl border border-teal/40 bg-teal/10 p-5 text-sm text-teal">¡Gracias por acompañarnos en la evolución de MySECOP! {detalle}</div> :
        <form onSubmit={enviar} className="space-y-4 p-5">
          <Field label="¿Qué quieres enviarnos?"><Select value={tipo} onChange={(e) => setTipo(e.target.value)}><option value="sugerencia">Sugerir una nueva funcionalidad</option><option value="error">Reportar un error</option></Select></Field>
          <Field label={tipo === "error" ? "Describe el error" : "Cuéntanos tu idea"}><Textarea required minLength={10} rows={7} value={mensaje} onChange={(e) => setMensaje(e.target.value)} placeholder={tipo === "error" ? "Qué ocurrió, en qué sección y qué esperabas que sucediera…" : "Qué funcionalidad te ayudaría a encontrar y ganar más procesos…"} /></Field>
          {estado === "error" ? <p className="text-xs text-red-500">{detalle}</p> : null}
          <Button type="submit" disabled={estado === "enviando"}>{estado === "enviando" ? "Enviando…" : "Enviar a MySECOP"}</Button>
        </form>}
    </Card>
  </div>;
}
