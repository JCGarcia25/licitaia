"use client";
/* Agente 4 · Preparador de Ofertas: proyectos, checklist, borradores y exportación. */
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { buttonStyles } from "@/lib/button-styles";
import { OfferReminderDialog } from "@/components/offer-reminder-dialog";
import { api, descargarBlob } from "@/lib/api";
import { Badge, Button, Card, CardHeader, EmptyState, Input, Select, Spinner, Textarea } from "@/components/ui";

type Project = {
  id: number; name: string; opportunity_id: number; status: string; version: number;
  updated_at: string; pendientes: number; is_saved: boolean; url_oficial?: string | null;
};
type ProjectDetail = {
  id: number; name: string; status: string; version: number; approved_by: string;
  opportunity: { id: number; objeto: string; entidad: string; url_oficial: string | null } | null;
  checklist: { item: string; tipo: string; estado: string; evidencia: string }[];
  cronograma: { tarea: string; plazo: string; fecha?: string; estimado?: boolean; vencido?: boolean; dias_disponibles?: number; estado?: "pendiente" | "listo" }[];
  borradores: { tipo: string; contenido: string; version: number; fecha: string }[];
  comentarios: { autor: string; texto: string; fecha: string }[];
};

const ESTADOS: Record<string, string> = { activo: "Activa", en_revision: "En revisión", aprobado: "Aprobada", presentado: "Presentada", archivado: "Archivada" };

export default function Ofertas() {
  const detail = useRef<HTMLDivElement>(null);
  const [lista, setLista] = useState<Project[] | null>(null);
  const [sel, setSel] = useState<ProjectDetail | null>(null);
  useEffect(() => { if (sel && window.matchMedia("(max-width: 1279px)").matches) detail.current?.scrollIntoView({ behavior: "instant", block: "start" }); }, [sel?.id]);
  const [reminder, setReminder] = useState<Project | null>(null);
  const [comentario, setComentario] = useState("");
  const [msg, setMsg] = useState("");

  const cargarLista = useCallback(async () => {
    setLista(await api<Project[]>("/api/offer-projects"));
  }, []);

  const abrir = useCallback(async (id: number) => {
    setSel(await api<ProjectDetail>(`/api/offer-projects/${id}`));
  }, []);

  useEffect(() => { cargarLista().catch(() => setLista([])); const id = Number(new URLSearchParams(window.location.search).get("oferta")); if (Number.isSafeInteger(id) && id > 0) void abrir(id).catch(() => setMsg("No pudimos abrir esta oferta. Selecciónala en la lista.")); }, [cargarLista, abrir]);

  async function guardarProceso(p: Project) {
    try { await api(`/api/opportunities/${p.opportunity_id}/saved`, { method: "PATCH", body: JSON.stringify({ saved: !p.is_saved }) }); await cargarLista(); setMsg(p.is_saved ? "Proceso retirado de guardados. Tu oferta se conserva." : "Proceso guardado. Aparecerá primero entre los resultados que coincidan con tu búsqueda."); }
    catch (e) { setMsg(e instanceof Error ? e.message : "No pudimos guardar el proceso."); }
  }

  async function toggleChecklist(index: number, estado: string) {
    if (!sel) return;
    const next = estado === "listo" ? "pendiente" : "listo";
    await api(`/api/offer-projects/${sel.id}/checklist`, { method: "PATCH", body: JSON.stringify({ index, estado: next }) });
    abrir(sel.id);
  }

  async function toggleCronograma(index: number, estado?: string) {
    if (!sel) return;
    await api(`/api/offer-projects/${sel.id}/cronograma`, { method: "PATCH", body: JSON.stringify({ index, estado: estado === "listo" ? "pendiente" : "listo" }) });
    await abrir(sel.id);
    await cargarLista();
  }

  async function generarBorrador(tipo: string) {
    if (!sel) return;
    try {
      await api(`/api/offer-projects/${sel.id}/borradores`, { method: "POST", body: JSON.stringify({ tipo }) });
      abrir(sel.id);
      setMsg(tipo === "respuestas_tecnicas" ? "" : "Borrador generado (v" + (sel.version + 1) + ").");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Error");
    }
  }

  async function cambiarEstado(status: string) {
    if (!sel) return;
    const r = await api<{ approved_by: string }>(`/api/offer-projects/${sel.id}/status`, {
      method: "POST", body: JSON.stringify({ status, approved_by: status === "aprobado" ? "Aprobación humana desde la app" : undefined }),
    });
    abrir(sel.id);
    await cargarLista();
    if (status === "aprobado") setMsg(`Oferta aprobada por ${r.approved_by}. Recuerda: la presentación en SECOP se realiza manualmente.`);
  }

  async function enviarComentario() {
    if (!sel || !comentario.trim()) return;
    await api(`/api/offer-projects/${sel.id}/comentarios`, { method: "POST", body: JSON.stringify({ texto: comentario }) });
    setComentario("");
    abrir(sel.id);
  }

  async function exportar(formato: string) {
    if (!sel) return;
    const blob = await api<Blob>(`/api/offer-projects/${sel.id}/export?formato=${formato}`);
    descargarBlob(blob, `oferta_${sel.id}.${formato}`);
  }

  async function eliminarOferta(id: number) {
    if (!window.confirm("¿Eliminar esta oferta del preparador? Esta acción no se puede deshacer.")) return;
    await api(`/api/offer-projects/${id}`, { method: "DELETE" });
    if (sel?.id === id) setSel(null);
    await cargarLista();
  }

  if (!lista) return <Spinner />;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Preparador de ofertas</h1>
        <p className="text-muted text-sm">Organiza la documentación de tu propuesta. Toda oferta requiere aprobación humana antes de presentarse.</p>
      </div>

      {reminder && <OfferReminderDialog key={reminder.id} projectId={reminder.id} name={reminder.name} onClose={() => setReminder(null)} />}
      <div className="offer-workspace grid gap-5 xl:grid-cols-3">
        {/* Lista de proyectos */}
        <div className="space-y-3">
          {lista.length === 0 ? (
            <Card><EmptyState title="Sin proyectos de oferta" body="Créalo desde una oportunidad en el listado." /></Card>
          ) : (
            lista.map((p) => (
              <Card key={p.id} className={`cursor-pointer p-4 transition hover:shadow-lift ${sel?.id === p.id ? "ring-2 ring-teal" : ""}`} >
                <button onClick={() => abrir(p.id)} className="w-full text-left">
                  <p className="text-sm font-semibold">{p.name}</p>
                  <p className="text-muted mt-1 text-[11px]">v{p.version} · {p.pendientes} {p.pendientes === 1 ? "documento pendiente" : "documentos pendientes"}</p>
                  <div className="mt-2 flex flex-wrap gap-2"><Badge tone={p.status === "aprobado" ? "green" : p.status === "archivado" ? "gray" : "blue"}>{ESTADOS[p.status] || p.status}</Badge>{p.is_saved && <Badge tone="purple">Proceso guardado</Badge>}</div>
                </button>
                <div className="offer-card-actions mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Button size="sm" variant="outline" onClick={() => guardarProceso(p)}>{p.is_saved ? "Dejar de guardar proceso" : "Guardar proceso"}</Button>
                  <Button size="sm" variant="outline" onClick={() => setReminder(p)}>Recordatorio de cierre</Button>
                  <Button size="sm" variant="ghost" className="text-red-600" onClick={() => eliminarOferta(p.id)}>Eliminar oferta</Button>
                  {p.url_oficial ? <a href={p.url_oficial} target="_blank" rel="noopener noreferrer" className={buttonStyles({ size: "sm", variant: "outline" })}>Ver en SECOP ↗</a> : null}
                </div>
              </Card>
            ))
          )}
          <p className="text-muted text-[11px]">¿Necesitas uno nuevo? <Link href="/app/oportunidades" className="text-teal underline underline-offset-2">Elige una oportunidad</Link>.</p>
        </div>

        {/* Detalle */}
        <div ref={detail} className="min-w-0 scroll-mt-28 space-y-5 xl:col-span-2">
          {!sel ? (
            <Card><EmptyState title="Selecciona un proyecto" body="Elige una de tus ofertas en la lista para revisar sus documentos y tareas." /></Card>
          ) : (
            <>
              <Card className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="font-bold">{sel.name}</h2>
                    {sel.opportunity ? (
                      <Link href={`/app/oportunidades/${sel.opportunity.id}`} className="text-muted text-xs hover:text-teal">
                        {sel.opportunity.entidad} — {sel.opportunity.objeto}
                      </Link>
                    ) : null}
                  </div>
                  <Select aria-label="Estado de la oferta" value={sel.status} onChange={(e) => cambiarEstado(e.target.value)} className="max-w-40">
                    {Object.entries(ESTADOS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </Select>
                </div>
                <div className="offer-export-actions mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 2xl:grid-cols-4">
                  <Button size="sm" variant="outline" onClick={() => exportar("docx")}>Exportar Word</Button>
                  <Button size="sm" variant="outline" onClick={() => exportar("xlsx")}>Exportar Excel</Button>
                  <Button size="sm" variant="outline" onClick={() => exportar("pdf")}>Exportar PDF</Button>
                  <Button size="sm" variant="outline" onClick={() => cambiarEstado("aprobado")}>Aprobar (persona autorizada)</Button>
                </div>
              </Card>

              {/* Checklist */}
              <Card>
                <CardHeader title="Checklist documental" subtitle="Marca los documentos listos" />
                <ul className="divide-y divide-[var(--border)]">
                  {sel.checklist.map((c, i) => (
                    <li key={i} className="flex flex-col items-start justify-between gap-2 px-5 py-3 text-sm sm:flex-row sm:items-center">
                      <button onClick={() => toggleChecklist(i, c.estado)} className="flex min-w-0 flex-1 items-center gap-2 text-left">
                        <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border text-[10px] ${c.estado === "listo" ? "border-teal bg-teal text-white" : "border-base"}`}>
                          {c.estado === "listo" ? "✓" : ""}
                        </span>
                        <span className={c.estado === "listo" ? "text-muted line-through" : ""}>{c.item}</span>
                      </button>
                      <Badge tone={c.tipo === "jurídico" ? "purple" : c.tipo === "financiero" ? "amber" : "blue"}>{c.tipo}</Badge>
                    </li>
                  ))}
                </ul>
              </Card>

              {/* Cronograma */}
              <Card>
                <CardHeader title="Cronograma interno sugerido" subtitle="Plan de trabajo calculado con la información disponible del proceso" />
                {(() => {
                  const avance = sel.cronograma.length ? Math.round(sel.cronograma.filter((c) => c.estado === "listo").length / sel.cronograma.length * 100) : 0;
                  return <div className="px-5 pt-3"><div className="flex items-center justify-between text-xs"><span className="font-medium">Avance del cronograma</span><span className="font-bold text-teal">{avance}%</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full bg-teal transition-all" style={{ width: `${avance}%` }} /></div></div>;
                })()}
                <p className="text-muted px-5 pt-3 text-xs">Las fechas se calculan hasta el cierre oficial cuando SECOP lo informa. Si no está disponible, verás plazos estimados relativos.</p>
                <ul className="divide-y divide-[var(--border)]">
                  {sel.cronograma.map((c, i) => (
                    <li key={i} className="flex flex-wrap justify-between gap-2 px-5 py-2 text-sm">
                      <button onClick={() => toggleCronograma(i, c.estado)} className="flex min-w-0 items-center gap-2 text-left"><span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border text-[10px] ${c.estado === "listo" ? "border-teal bg-teal text-white" : "border-base"}`}>{c.estado === "listo" ? "✓" : ""}</span><span className={`text-muted ${c.estado === "listo" ? "line-through" : ""}`}>{c.tarea}</span></button>
                      <span className={`font-medium ${c.vencido ? "text-red-500" : "text-[var(--text)]"}`}>{c.plazo}{c.estimado ? " · estimado" : ""}{c.vencido ? " · vencido" : ""}</span>
                    </li>
                  ))}
                </ul>
              </Card>

              {/* Borradores */}
              <Card>
                <CardHeader
                  title="Borradores"
                  subtitle="Las respuestas técnicas se generan solo con información que tú proporcionas"
                  action={
                    <div className="flex w-full flex-wrap gap-2 sm:w-auto">
                      <Button size="sm" variant="outline" onClick={() => generarBorrador("carta_presentacion")}>Carta de presentación</Button>
                      <Button size="sm" variant="outline" onClick={() => generarBorrador("matriz_cumplimiento")}>Matriz</Button>
                      <Button size="sm" variant="outline" onClick={() => generarBorrador("respuestas_tecnicas")}>Respuestas técnicas</Button>
                    </div>
                  }
                />
                <div className="space-y-3 p-5">
                  {sel.borradores.length === 0 ? (
                    <EmptyState title="Sin borradores aún" />
                  ) : (
                    sel.borradores.slice().reverse().map((b, i) => (
                      <details key={i} className="rounded-lg border border-base px-4 py-3" open={i === 0}>
                        <summary className="cursor-pointer text-xs font-medium">{({ carta_presentacion: "Carta de presentación", matriz_cumplimiento: "Matriz de cumplimiento", respuestas_tecnicas: "Respuestas técnicas" } as Record<string, string>)[b.tipo] || b.tipo} · v{b.version} · {b.fecha}</summary>
                        <pre className="text-muted mt-2 whitespace-pre-wrap text-[11px]">{b.contenido}</pre>
                      </details>
                    ))
                  )}
                  <Textarea
                    aria-label="Información para respuestas técnicas"
                    placeholder="Contenido para respuestas técnicas (usa información verificada de tu empresa)…"
                    value={comentario}
                    onChange={(e) => setComentario(e.target.value)}
                  />
                  <p className="text-muted text-[11px]">
                    Nota: MySECOP nunca genera certificaciones, experiencia ni firmas. La presentación en SECOP es manual.
                  </p>
                </div>
              </Card>

              {/* Comentarios */}
              <Card>
                <CardHeader title="Comentarios y aprobaciones" />
                <div className="space-y-2 p-5">
                  {sel.comentarios.map((c, i) => (
                    <p key={i} className="text-muted text-xs"><span className="font-medium text-[var(--text)]">{c.autor}:</span> {c.texto} <span className="text-[10px]">({c.fecha})</span></p>
                  ))}
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Input aria-label="Nuevo comentario" value={comentario} onChange={(e) => setComentario(e.target.value)} placeholder="Añadir comentario…" />
                    <Button size="sm" onClick={enviarComentario} className="shrink-0">Comentar</Button>
                  </div>
                </div>
              </Card>
            </>
          )}
          {msg ? <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"><div className="surface-card w-full max-w-md p-7 text-center"><div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-teal/15 text-3xl text-teal">✓</div><h2 className="mt-4 text-xl font-bold">Información del preparador</h2><p className="text-muted mt-2 text-sm">{msg}</p><Button className="mt-6 w-full" onClick={() => setMsg("")}>Continuar en MySECOP</Button></div></div> : null}
        </div>
      </div>
    </div>
  );
}
