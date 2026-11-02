"use client";
import { FormEvent, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button, Card, CardHeader, Field, Input, Textarea } from "@/components/ui";

export default function LicenciaComercialPage() {
  const [nombre, setNombre] = useState("");
  const [empresa, setEmpresa] = useState("");
  const [email, setEmail] = useState("");
  const [vendedores, setVendedores] = useState("2");
  const [detalle, setDetalle] = useState("");
  const [estado, setEstado] = useState<"idle" | "enviando" | "enviado" | "error">("idle");
  const [mensaje, setMensaje] = useState("");

  async function enviar(evento: FormEvent) {
    evento.preventDefault(); setEstado("enviando"); setMensaje("");
    try {
      const respuesta = await api<{ nota?: string }>("/api/contact", { method: "POST", body: JSON.stringify({
        nombre, email, mensaje: `[LICENCIA CORPORATIVA]\nEmpresa: ${empresa}\nVendedores: ${vendedores}\n\nNecesidad: ${detalle}`,
      }) });
      setEstado("enviado"); setMensaje(respuesta.nota || "Recibimos tus datos. Te contactaremos para preparar una propuesta comercial.");
    } catch (error) { setEstado("error"); setMensaje(error instanceof Error ? error.message : "No fue posible enviar la solicitud."); }
  }

  return <div className="mx-auto max-w-2xl space-y-6"><Link href="/app/ayuda" className="text-muted text-sm hover:text-teal">← Volver a sugerencias y reportes</Link><div><h1 className="mt-3 text-2xl font-bold">Licencia comercial MySECOP</h1><p className="text-muted mt-1">Ahorra al habilitar MySECOP para todo tu equipo comercial.</p></div><Card><CardHeader title="Hablemos de tu equipo" subtitle="MySECOP evoluciona contigo. Cuéntanos tu necesidad y te acompañaremos personalmente." />{estado === "enviado" ? <div className="m-5 rounded-xl border border-teal/40 bg-teal/10 p-5 text-sm text-teal">Solicitud recibida. {mensaje}</div> : <form onSubmit={enviar} className="space-y-4 p-5"><Field label="Tu nombre"><Input required minLength={2} value={nombre} onChange={(e) => setNombre(e.target.value)} /></Field><Field label="Empresa"><Input required minLength={2} value={empresa} onChange={(e) => setEmpresa(e.target.value)} /></Field><Field label="Correo corporativo"><Input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field><Field label="Número de vendedores"><Input required type="number" min="1" value={vendedores} onChange={(e) => setVendedores(e.target.value)} /></Field><Field label="¿Qué necesitas?"><Textarea required minLength={10} rows={5} value={detalle} onChange={(e) => setDetalle(e.target.value)} placeholder="Cuéntanos sobre tu equipo, sectores y necesidades…" /></Field>{estado === "error" ? <p className="text-xs text-red-500">{mensaje}</p> : null}<Button type="submit" disabled={estado === "enviando"}>{estado === "enviando" ? "Enviando…" : "Solicitar licencia corporativa"}</Button></form>}</Card></div>;
}
