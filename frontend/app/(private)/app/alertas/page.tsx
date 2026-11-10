"use client";
/* Sistema de alertas: bandeja, preferencias y ciclo manual. */
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, Spinner } from "@/components/ui";

type Alerta = { id: number; tipo: string; title: string; body: string; opportunity_id: number | null; read_at: string | null; created_at: string };
type Prefs = { email_enabled: boolean; email_to: string; high_score_threshold: number; close_days: number[]; digest_hour: number };

const TIPO_TONE: Record<string, "green" | "amber" | "blue" | "purple"> = {
  alta_compatibilidad: "green", cierre_proximo: "amber", nueva: "blue", documento: "purple", resumen_diario: "blue",
};

export default function Alertas() {
  const [alertas, setAlertas] = useState<Alerta[] | null>(null);
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [msg, setMsg] = useState("");
  const [soloNoLeidas, setSoloNoLeidas] = useState(false);
  const [emailModal, setEmailModal] = useState(false);
  const router = useRouter();

  const cargar = useCallback(async () => {
    setAlertas(await api<Alerta[]>(`/api/alerts?solo_no_leidas=${soloNoLeidas}`));
    setPrefs(await api<Prefs>("/api/alerts/prefs"));
  }, [soloNoLeidas]);

  useEffect(() => { cargar().catch(() => { setAlertas([]); setPrefs({ email_enabled: false, email_to: "", high_score_threshold: 70, close_days: [10, 5, 1], digest_hour: 7 }); }); }, [cargar]);

  async function guardarPrefs() {
    if (!prefs) return;
    const result = await api<{ alertas_creadas?: number }>("/api/alerts/prefs", { method: "PUT", body: JSON.stringify(prefs) });
    await cargar();
    const creadas = result.alertas_creadas || 0;
    setMsg(creadas
      ? `Tus preferencias se guardaron y se generaron ${creadas} alerta(s) nuevas según tu umbral.`
      : "Tus preferencias se guardaron correctamente. Las alertas existentes siguen activas y el nuevo umbral se aplicará a las próximas oportunidades.");
  }

  async function restablecerPrefs() {
    await api("/api/alerts/prefs", { method: "DELETE" });
    setPrefs({ email_enabled: false, email_to: "", high_score_threshold: 70, close_days: [10, 5, 1], digest_hour: 7 });
    setMsg("Las preferencias se restablecieron a su configuración inicial.");
  }

  async function ejecutarCiclo() {
    const r = await api<{ alertas_creadas: number; recordatorios_cierre: number; correo_enviado: boolean }>("/api/alerts/digest", { method: "POST" });
    setMsg(`Actualización completada: ${r.alertas_creadas} alerta(s) nuevas y ${r.recordatorios_cierre} recordatorio(s) de cierre. ${r.correo_enviado ? "Enviamos el resumen al correo configurado." : "Tus alertas están disponibles dentro de MySECOP."}`);
    await cargar();
  }

  async function enviarResumenAhora() {
    try {
      if (!prefs?.email_enabled) {
        setMsg("Activa primero el resumen por correo y confirma al menos un destinatario.");
        return;
      }
      await api("/api/alerts/prefs", { method: "PUT", body: JSON.stringify(prefs) });
      const r = await api<{ correo_enviado: boolean }>("/api/alerts/digest", { method: "POST" });
      setMsg(r.correo_enviado ? "Enviamos el resumen a los destinatarios configurados." : "No fue posible enviar el resumen. Verifica la configuración de correo del servidor.");
    } catch (e) { setMsg(e instanceof Error ? e.message : "No fue posible enviar el resumen."); }
  }

  async function marcarTodo() {
    await api("/api/alerts/read-all", { method: "POST" });
    cargar();
  }

  async function abrirAlerta(a: Alerta) {
    if (!a.read_at) {
      await api(`/api/alerts/${a.id}/read`, { method: "POST" });
      setAlertas((items) => items ? items.map((item) => item.id === a.id ? { ...item, read_at: new Date().toISOString() } : item) : items);
    }
    if (a.opportunity_id) router.push(`/app/oportunidades/${a.opportunity_id}?from=alertas`);
  }

  if (!alertas || !prefs) return <Spinner />;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Alertas</h1>
          <p className="text-muted text-sm">Notificaciones in-app y resumen diario opcional por correo (07:00, hora de Bogotá).</p>
        </div>
        <div className="flex w-full flex-wrap gap-2 sm:w-auto">
          <Button size="sm" variant="outline" onClick={ejecutarCiclo}>Actualizar alertas ahora</Button>
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
              <Card key={a.id} className={`p-4 transition ${a.read_at ? "opacity-65" : "border-teal/50 shadow-[0_0_0_1px_rgba(45,212,191,.18)]"}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge tone={TIPO_TONE[a.tipo] || "blue"}>{a.tipo}</Badge>
                    {!a.read_at ? <span className="rounded-full bg-teal/15 px-2 py-0.5 text-[10px] font-semibold text-teal">Nueva</span> : <span className="text-muted text-[10px]">Leída</span>}
                  </div>
                  <span className="text-muted text-[11px]">{new Date(a.created_at).toLocaleString("es-CO")}</span>
                </div>
                {a.opportunity_id ? (
                  <button type="button" onClick={() => abrirAlerta(a)} className="mt-2 block text-left text-sm font-medium hover:text-teal">{a.title}</button>
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
              <label className="flex items-start gap-2 text-sm">
                <input type="checkbox" checked={prefs.email_enabled} onChange={(e) => { const enabled = e.target.checked; setPrefs({ ...prefs, email_enabled: enabled }); if (enabled) setEmailModal(true); }} className="accent-teal" />
                Enviar resumen por correo
              </label>
              {prefs.email_enabled ? <p className="text-muted -mt-2 text-xs">El resumen se enviará a <strong className="text-slate-200">{prefs.email_to || "tu correo registrado"}</strong>.</p> : null}
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
              <Button onClick={enviarResumenAhora} variant="outline" className="w-full">Enviar resumen ahora</Button>
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
      {emailModal ? <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4" role="dialog" aria-modal="true">
        <div className="surface-card w-full max-w-md p-7">
          <h2 className="text-xl font-bold">¿A qué correo enviamos tus alertas?</h2>
          <p className="text-muted mt-2 text-sm">Escribe uno o varios correos separados por coma. El resumen programado se enviará a todos los destinatarios guardados.</p>
          <Input type="text" className="mt-5" value={prefs.email_to} onChange={(e) => setPrefs({ ...prefs, email_to: e.target.value })} placeholder="correo@empresa.com, equipo@empresa.com" />
          <div className="mt-5 flex gap-2"><Button variant="outline" className="flex-1" onClick={() => { setPrefs({ ...prefs, email_enabled: false }); setEmailModal(false); }}>Cancelar</Button><Button className="flex-1" onClick={() => setEmailModal(false)}>Confirmar correo</Button></div>
        </div>
      </div> : null}
    </div>
  );
}
