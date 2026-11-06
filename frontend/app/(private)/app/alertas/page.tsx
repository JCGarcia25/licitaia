"use client";
/* Sistema de alertas: bandeja, preferencias y ciclo manual. */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, Spinner } from "@/components/ui";

type Alerta = { id: number; tipo: string; title: string; body: string; opportunity_id: number | null; read_at: string | null; created_at: string };
type Prefs = { email_enabled: boolean; high_score_threshold: number; close_days: number[]; digest_hour: number };

const TIPO_TONE: Record<string, "green" | "amber" | "blue" | "purple"> = {
  alta_compatibilidad: "green", cierre_proximo: "amber", nueva: "blue", documento: "purple", resumen_diario: "blue",
};

export default function Alertas() {
  const [alertas, setAlertas] = useState<Alerta[] | null>(null);
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [msg, setMsg] = useState("");
  const [soloNoLeidas, setSoloNoLeidas] = useState(false);

  const cargar = useCallback(async () => {
    setAlertas(await api<Alerta[]>(`/api/alerts?solo_no_leidas=${soloNoLeidas}`));
    setPrefs(await api<Prefs>("/api/alerts/prefs"));
  }, [soloNoLeidas]);

  useEffect(() => { cargar().catch(() => { setAlertas([]); setPrefs({ email_enabled: false, high_score_threshold: 70, close_days: [10, 5, 1], digest_hour: 7 }); }); }, [cargar]);

  async function guardarPrefs() {
    if (!prefs) return;
    const result = await api<{ alertas_creadas?: number }>("/api/alerts/prefs", { method: "PUT", body: JSON.stringify(prefs) });
    await cargar();
    const creadas = result.alertas_creadas || 0;
    setMsg(creadas
      ? `Tus preferencias se guardaron y se generaron ${creadas} alerta(s) según tu nuevo umbral.`
      : "Tus preferencias se guardaron. Aún no hay oportunidades puntuadas que cumplan el umbral seleccionado.");
  }

  async function restablecerPrefs() {
    await api("/api/alerts/prefs", { method: "DELETE" });
    setPrefs({ email_enabled: false, high_score_threshold: 70, close_days: [10, 5, 1], digest_hour: 7 });
    setMsg("Las preferencias se restablecieron a su configuración inicial.");
  }

  async function ejecutarCiclo() {
    const r = await api<{ alertas_creadas: number; recordatorios_cierre: number; correo_enviado: boolean }>("/api/alerts/digest", { method: "POST" });
    setMsg(`Revisión completada: ${r.alertas_creadas} alerta(s) de compatibilidad y ${r.recordatorios_cierre} recordatorio(s) de cierre. ${r.correo_enviado ? "El resumen fue enviado a tu correo." : "Las alertas están disponibles dentro de MySECOP."}`);
    await cargar();
  }

  async function marcarTodo() {
    await api("/api/alerts/read-all", { method: "POST" });
    cargar();
  }

  if (!alertas || !prefs) return <Spinner />;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Alertas</h1>
          <p className="text-muted text-sm">Notificaciones in-app y resumen diario opcional por correo (07:00, hora de Bogotá).</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={ejecutarCiclo}>Ejecutar ciclo ahora</Button>
          <Button size="sm" variant="ghost" onClick={marcarTodo}>Marcar todo leído</Button>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          <label className="text-muted flex items-center gap-2 text-xs">
            <input type="checkbox" checked={soloNoLeidas} onChange={(e) => setSoloNoLeidas(e.target.checked)} className="accent-teal" />
            Solo no leídas
          </label>
          {alertas.length === 0 ? (
            <Card><EmptyState title={soloNoLeidas ? "No tienes alertas pendientes" : "Aún no hay alertas"} body={soloNoLeidas ? "Cuando exista una alerta nueva aparecerá aquí." : "MySECOP mostrará aquí oportunidades compatibles y recordatorios importantes para tu empresa."} /></Card>
          ) : (
            alertas.map((a) => (
              <Card key={a.id} className={`p-4 ${a.read_at ? "opacity-70" : ""}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge tone={TIPO_TONE[a.tipo] || "blue"}>{a.tipo}</Badge>
                    {!a.read_at ? <span className="h-2 w-2 rounded-full bg-teal" /> : null}
                  </div>
                  <span className="text-muted text-[11px]">{new Date(a.created_at).toLocaleString("es-CO")}</span>
                </div>
                {a.opportunity_id ? (
                  <Link href={`/app/oportunidades/${a.opportunity_id}`} className="mt-2 block text-sm font-medium hover:text-teal">{a.title}</Link>
                ) : (
                  <p className="mt-2 text-sm font-medium">{a.title}</p>
                )}
                <p className="text-muted mt-1 text-xs">{a.body}</p>
              </Card>
            ))
          )}
        </div>

        <Card>
          <CardHeader title="Preferencias de alertas" />
          {prefs ? (
            <div className="space-y-4 p-5">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={prefs.email_enabled} onChange={(e) => setPrefs({ ...prefs, email_enabled: e.target.checked })} className="accent-teal" />
                Enviar resumen por correo
              </label>
              <Field label="Umbral de alta compatibilidad (%)" hint="Alerta cuando el puntaje del agente supera este valor.">
                <Input type="number" min={0} max={100} value={prefs.high_score_threshold}
                  onChange={(e) => setPrefs({ ...prefs, high_score_threshold: Number(e.target.value) })} />
              </Field>
              <Field label="Recordatorios de cierre (días antes)" hint="Separados por coma: 10, 5, 1.">
                <Input value={(prefs.close_days || []).join(", ")}
                  onChange={(e) => setPrefs({ ...prefs, close_days: e.target.value.split(",").map((s) => parseInt(s.trim(), 10)).filter((n) => !isNaN(n)) })} />
              </Field>
              <Field label="Hora del resumen diario" hint="Hora local de Bogotá (0-23).">
                <Input type="number" min={0} max={23} value={prefs.digest_hour}
                  onChange={(e) => setPrefs({ ...prefs, digest_hour: Number(e.target.value) })} />
              </Field>
              <Button onClick={guardarPrefs} className="w-full">Guardar preferencias</Button>
              <Button onClick={restablecerPrefs} variant="outline" className="w-full">Restablecer preferencias</Button>
              <p className="text-muted text-[11px] leading-relaxed">Las alertas dentro de MySECOP siempre están activas. El resumen por correo es opcional.</p>
            </div>
          ) : null}
        </Card>
      </div>
      {msg ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4" role="dialog" aria-modal="true" aria-label="Mensaje de alertas">
          <div className="surface-card w-full max-w-md p-7 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-teal/15 text-3xl text-teal">✓</div>
            <h2 className="mt-4 text-xl font-bold">Preferencias de alertas</h2>
            <p className="text-muted mt-2 text-sm">{msg}</p>
            <Button className="mt-6 w-full" onClick={() => setMsg("")}>Continuar en MySECOP</Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
