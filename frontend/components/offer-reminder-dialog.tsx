"use client";
import { useEffect, useId, useRef, useState } from "react";
import { api, apiBackground } from "@/lib/api";
import { Button, Field, Input, Spinner } from "@/components/ui";

type Reminder = { status: string; scheduled_at: string; sent_at: string | null; retry_at: string | null; last_error: string | null };
type State = { can_schedule: boolean; can_cancel: boolean; reason: string | null; message: string | null; closing_at: string | null; recipient: string; timezone: string; reminder: Reminder | null };
const format = (value: string) => new Intl.DateTimeFormat("es-CO", { timeZone: "America/Bogota", dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
function parts(value: string) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("sv-SE", { timeZone: "America/Bogota", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(value)).map(x => [x.type, x.value]));
  return { day: `${p.year}-${p.month}-${p.day}`, hour: `${p.hour}:${p.minute}` };
}
const STATES: Record<string, string> = { SCHEDULED: "Programado", SENDING: "Enviando", RETRY: "Reintentando la conexión de correo", SENT: "Enviado al servidor de correo", CANCELLED: "Cancelado", BLOCKED: "Requiere revisión", FAILED: "No se pudo enviar", UNKNOWN: "Envío sin confirmar" };
const ERRORS: Record<string, string> = { NO_CLOSING_DATE: "El proceso ya no tiene una fecha de cierre identificada.", CLOSING_DATE_CHANGED: "La fecha de cierre cambió. Revisa el nuevo plazo y vuelve a programar el recordatorio.", PROCESS_CLOSED: "El proceso cerró o fue cancelado antes del envío.", INACTIVE_OFFER: "La oferta fue archivada o presentada.", ACCOUNT_EMAIL_CHANGED: "El correo cambió o requiere verificación.", PRO_REQUIRED: "La cuenta ya no tiene acceso Pro.", DELIVERY_UNCONFIRMED: "No pudimos confirmar si el correo salió. No lo reenviaremos automáticamente para evitar duplicados. Si lo programas de nuevo, podrías recibirlo más de una vez.", EMAIL_CONNECTION: "No se pudo conectar al servicio de correo.", EMAIL_UNAVAILABLE: "El servicio de correo no está disponible.", RECIPIENT_REJECTED: "El servidor rechazó el destinatario.", EMAIL_CONFIGURATION: "El servicio de correo requiere revisión de soporte.", MESSAGE_REJECTED: "El servidor de correo rechazó el mensaje." };

export function OfferReminderDialog({ projectId, name, onClose }: { projectId: number; name: string; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null), titleId = useId();
  const [data, setData] = useState<State | null>(null), [day, setDay] = useState(""), [hour, setHour] = useState("");
  const [error, setError] = useState(""), [message, setMessage] = useState(""), [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    dialog.current?.showModal(); document.body.style.overflow = "hidden";
    apiBackground<State>(`/api/offer-projects/${projectId}/closing-reminder`).then(value => {
      if (!active) return;
      setData(value);
      if (value.reminder) { const p = parts(value.reminder.scheduled_at); setDay(p.day); setHour(p.hour); }
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : "No pudimos consultar el recordatorio."); });
    return () => { active = false; document.body.style.overflow = overflow; previous?.focus(); };
  }, [projectId]);
  async function save(event: React.FormEvent) {
    event.preventDefault(); setError(""); setMessage("");
    const when = new Date(`${day}T${hour}:00-05:00`);
    if (!data?.closing_at || !Number.isFinite(when.getTime()) || when.getTime() <= Date.now() || when.getTime() >= new Date(data.closing_at).getTime()) { setError("Elige una fecha y hora futuras, anteriores al cierre del proceso."); return; }
    setBusy(true);
    try {
      const value = await api<State>(`/api/offer-projects/${projectId}/closing-reminder`, { method: "PUT", body: JSON.stringify({ scheduled_at: when.toISOString() }) });
      setData(value); setMessage(`Recordatorio programado para el ${format(when.toISOString())}, hora de Colombia.`);
    } catch (e) { setError(e instanceof Error ? e.message : "No pudimos programar el recordatorio."); }
    finally { setBusy(false); }
  }
  async function cancel() {
    setBusy(true); setError(""); setMessage("");
    try { setData(await api<State>(`/api/offer-projects/${projectId}/closing-reminder`, { method: "DELETE" })); setMessage("Recordatorio cancelado. No se enviará el correo programado."); }
    catch (e) { setError(e instanceof Error ? e.message : "No pudimos cancelar el recordatorio."); }
    finally { setBusy(false); }
  }
  return <dialog ref={dialog} aria-labelledby={titleId} onCancel={e => { if (busy) e.preventDefault(); }} onClose={onClose} className="offer-reminder-dialog surface-card fixed inset-0 m-auto h-fit max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg overflow-y-auto p-5 text-[var(--text)] shadow-2xl backdrop:bg-slate-950/60 sm:p-7">
    <div className="flex items-start justify-between gap-3"><h2 id={titleId} className="text-lg font-bold">Recordatorio de cierre por correo</h2><button type="button" disabled={busy} onClick={() => dialog.current?.close()} aria-label="Cerrar recordatorio" className="min-h-11 min-w-11 rounded-lg border border-base px-2">✕</button></div>
    <p className="text-muted mt-2 break-words text-sm">{name}</p>
    {!data && !error && <Spinner label="Consultando el cierre del proceso…" />}
    {data && <div className="mt-5 space-y-4">
      {data.closing_at && <p className="rounded-lg border border-base p-3 text-sm"><strong>Cierre identificado:</strong> {format(data.closing_at)} · hora de Colombia.</p>}
      {data.reminder && <div className="space-y-2 rounded-lg border border-base p-3 text-sm"><p><strong>{STATES[data.reminder.status] || data.reminder.status}</strong> · {format(data.reminder.scheduled_at)}</p>{data.reminder.status === "RETRY" && data.reminder.retry_at && <p>Próximo intento: {format(data.reminder.retry_at)}, hora de Colombia.</p>}{data.reminder.last_error && <p>{ERRORS[data.reminder.last_error] || "El recordatorio requiere revisión. Puedes volver a programarlo."}</p>}</div>}
      {!data.can_schedule ? <div role="status" className="rounded-lg border border-amber-400/50 bg-amber-100/40 p-4 text-sm dark:bg-amber-950/30"><p>{data.message}</p>{data.reason === "EMAIL_UNVERIFIED" && <a href="/app/alertas" className="mt-3 inline-flex min-h-11 items-center font-semibold underline">Verificar mi correo</a>}</div> : <form onSubmit={save} className="space-y-4">
        <p className="break-words text-sm">Se enviará al correo de tu cuenta: <strong>{data.recipient}</strong>.</p>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="Fecha del recordatorio"><Input type="date" required min={parts(new Date().toISOString()).day} max={parts(data.closing_at!).day} value={day} onChange={e => setDay(e.target.value)} /></Field><Field label="Hora del recordatorio (Colombia)"><Input type="time" required value={hour} onChange={e => setHour(e.target.value)} /></Field></div>
        <p className="text-muted text-xs leading-relaxed">Hora de Colombia (UTC−5). El servicio revisa los envíos cada minuto; elige suficiente anticipación al cierre. Confirma siempre el plazo en SECOP.</p>
        <Button type="submit" disabled={busy || data.reminder?.status === "SENDING"} className="w-full">{busy ? "Guardando…" : data.reminder && data.reminder.status !== "CANCELLED" ? "Actualizar recordatorio" : "Programar recordatorio"}</Button>
      </form>}
      {data.can_cancel && <Button variant="outline" disabled={busy} onClick={cancel} className="w-full">Cancelar recordatorio</Button>}
    </div>}
    {error && <p role="alert" className="mt-4 text-sm text-red-700 dark:text-red-300">{error}</p>}
    {message && <p role="status" className="mt-4 text-sm font-medium text-teal">{message}</p>}
  </dialog>;
}
