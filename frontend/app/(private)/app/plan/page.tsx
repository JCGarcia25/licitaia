"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button, Card, CardHeader } from "@/components/ui";

type Billing = { plan: string; nombre: string; es_pro: boolean; status: string; usage: { used: number; limit: number } };

const free = ["Búsqueda en SECOP y filtros", "Compatibilidad básica con tu perfil", "Guardar y descartar oportunidades"];
const pro = ["Todo lo incluido en Free", "Análisis de pliegos y anexos", "Evaluación de viabilidad", "Alertas y resumen por correo", "Preparador de ofertas y exportación", "Importación de documentos públicos"];

export default function PlanPage() {
  const [billing, setBilling] = useState<Billing | null>(null);
  const [msg, setMsg] = useState("");
  useEffect(() => { api<Billing>("/api/billing").then(setBilling).catch(() => undefined); }, []);
  async function solicitarPro() {
    try {
      const result = await api<{ status: string; checkout_url?: string }>("/api/billing/subscribe", { method: "POST", body: JSON.stringify({ plan: "profesional" }) });
      if (result.checkout_url) { window.location.href = result.checkout_url; return; }
      setMsg(result.status === "pendiente_pago" ? "Solicitud registrada. El acceso Pro se activa al confirmar el pago." : "Plan actualizado.");
      const next = await api<Billing>("/api/billing"); setBilling(next);
    } catch (e) { setMsg(e instanceof Error ? e.message : "No fue posible iniciar la suscripción."); }
  }
  return <div className="space-y-6">
    <div><Link href="/app" className="text-sm text-teal hover:underline">← Volver al dashboard</Link><h1 className="mt-3 text-2xl font-bold">Tu plan MySECOP</h1><p className="text-muted mt-1">Empieza gratis y desbloquea el flujo completo cuando estés listo para competir.</p></div>
    {billing && <Card className="border-teal/30"><CardHeader title={billing.nombre} subtitle={`Consumo de análisis: ${billing.usage.used}/${billing.usage.limit} este mes · Estado: ${billing.status}`} /></Card>}
    <div className="grid gap-5 md:grid-cols-2">
      <Card><CardHeader title="MySECOP Free" subtitle="Para descubrir oportunidades y crear el hábito." /><ul className="mt-4 space-y-2 text-sm">{free.map(x => <li key={x}>✓ {x}</li>)}</ul></Card>
      <Card className="border-teal shadow-lg shadow-teal/10"><CardHeader title="MySECOP Pro · $59.900/mes" subtitle="Para analizar, decidir y preparar propuestas más rápido." /><ul className="mt-4 space-y-2 text-sm">{pro.map(x => <li key={x} className="text-teal">✓ <span className="text-[var(--text)]">{x}</span></li>)}</ul><Button className="mt-6 w-full" onClick={solicitarPro}>{billing?.es_pro ? "Plan Pro activo" : "Desbloquear MySECOP Pro"}</Button>{msg && <p className="mt-3 text-xs text-muted">{msg}</p>}</Card>
    </div>
    <p className="text-muted text-xs">El pago se procesa mediante la pasarela configurada por el administrador. MySECOP nunca presenta ofertas automáticamente en SECOP.</p>
  </div>;
}
