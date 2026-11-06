"use client";
import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
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
      <form onSubmit={enviar} className="space-y-4 p-5">
          <Field label="¿Qué quieres enviarnos?"><Select value={tipo} onChange={(e) => setTipo(e.target.value)}><option value="sugerencia">Sugerir una nueva funcionalidad</option><option value="error">Reportar un error</option></Select></Field>
          <Field label={tipo === "error" ? "Describe el error" : "Cuéntanos tu idea"}><Textarea required minLength={10} rows={7} value={mensaje} onChange={(e) => setMensaje(e.target.value)} placeholder={tipo === "error" ? "Qué ocurrió, en qué sección y qué esperabas que sucediera…" : "Qué funcionalidad te ayudaría a encontrar y ganar más procesos…"} /></Field>
          {estado === "error" ? <p className="text-xs text-red-500">{detalle}</p> : null}
          <Button type="submit" disabled={estado === "enviando"}>{estado === "enviando" ? "Enviando…" : "Enviar a MySECOP"}</Button>
      </form>
    </Card>
    <Card className="border-teal/40 bg-teal/5"><CardHeader title="¿Requieres una licencia corporativa? Ahorra más" subtitle="Si quieres pagar una suscripción para cada vendedor de tu equipo, hablemos de una licencia comercial a tu medida." action={<Link href="/app/licencia-comercial" className="rounded-xl bg-teal px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-teal-light">Hablar con nosotros</Link>} /><p className="text-muted px-5 py-4 text-sm">Cuéntanos cuántas personas usarán MySECOP y te acompañaremos a elegir la mejor opción para tu empresa.</p></Card>
    {estado === "enviado" ? (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4" role="dialog" aria-modal="true" aria-label="Solicitud recibida">
        <div className="surface-card w-full max-w-md p-7 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-teal/15 text-3xl text-teal">✓</div>
          <h2 className="mt-4 text-xl font-bold">Solicitud recibida</h2>
          <p className="text-muted mt-2 text-sm">{detalle || "Recibimos tus datos. Te contactaremos para preparar una propuesta comercial."}</p>
          <Button className="mt-6 w-full" onClick={() => { setEstado("idle"); setDetalle(""); setMensaje(""); }}>Continuar en MySECOP</Button>
        </div>
      </div>
    ) : null}
  </div>;
}
