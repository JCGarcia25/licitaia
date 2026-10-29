"use client";
/* Agente 4 · Preparador de Ofertas: proyectos, checklist, borradores y exportación. */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, descargarBlob } from "@/lib/api";
import { Badge, Button, Card, CardHeader, EmptyState, Input, Select, Spinner, Textarea } from "@/components/ui";

type Project = {
  id: number; name: string; opportunity_id: number; status: string; version: number;
  updated_at: string; pendientes: number;
};
type ProjectDetail = {
  id: number; name: string; status: string; version: number; approved_by: string;
  opportunity: { id: number; objeto: string; entidad: string; url_oficial: string | null } | null;
  checklist: { item: string; tipo: string; estado: string; evidencia: string }[];
  cronograma: { tarea: string; plazo: string }[];
  borradores: { tipo: string; contenido: string; version: number; fecha: string }[];
  comentarios: { autor: string; texto: string; fecha: string }[];
};

const ESTADOS = ["activo", "en_revision", "aprobado", "presentado", "archivado"];

export default function Ofertas() {
  const [lista, setLista] = useState<Project[] | null>(null);
  const [sel, setSel] = useState<ProjectDetail | null>(null);
  const [comentario, setComentario] = useState("");
  const [msg, setMsg] = useState("");

  const cargarLista = useCallback(async () => {
    setLista(await api<Project[]>("/api/offer-projects"));
  }, []);

  const abrir = useCallback(async (id: number) => {
    setSel(await api<ProjectDetail>(`/api/offer-projects/${id}`));
  }, []);

  useEffect(() => { cargarLista().catch(() => setLista([])); }, [cargarLista]);

  async function toggleChecklist(index: number, estado: string) {
    if (!sel) return;
    const next = estado === "listo" ? "pendiente" : "listo";
    await api(`/api/offer-projects/${sel.id}/checklist`, { method: "PATCH", body: JSON.stringify({ index, estado: next }) });
    abrir(sel.id);
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

  if (!lista) return <Spinner />;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Preparador de Ofertas</h1>
        <p className="text-muted text-sm">Organiza la documentación de tu propuesta. Toda oferta requiere aprobación humana antes de presentarse.</p>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* Lista de proyectos */}
        <div className="space-y-3">
          {lista.length === 0 ? (
            <Card><EmptyState title="Sin proyectos de oferta" body="Créalo desde una oportunidad en el listado." /></Card>
          ) : (
            lista.map((p) => (
              <Card key={p.id} className={`cursor-pointer p-4 transition hover:shadow-lift ${sel?.id === p.id ? "ring-2 ring-teal" : ""}`} >
                <button onClick={() => abrir(p.id)} className="w-full text-left">
                  <p className="text-sm font-semibold">{p.name}</p>
                  <p className="text-muted mt-1 text-[11px]">v{p.version} · {p.pendientes} pendiente(s) de checklist</p>
                  <div className="mt-2"><Badge tone={p.status === "aprobado" ? "green" : p.status === "archivado" ? "gray" : "blue"}>{p.status}</Badge></div>
                </button>
              </Card>
            ))
          )}
          <p className="text-muted text-[11px]">¿Necesitas uno nuevo? <Link href="/app/oportunidades" className="text-teal hover:underline">Elige una oportunidad</Link>.</p>
        </div>

        {/* Detalle */}
        <div className="space-y-5 lg:col-span-2">
          {!sel ? (
            <Card><EmptyState title="Selecciona un proyecto" body="A la izquierda están tus proyectos de propuesta." /></Card>
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
                  <Select value={sel.status} onChange={(e) => cambiarEstado(e.target.value)} className="max-w-40">
                    {ESTADOS.map((s) => <option key={s} value={s}>{s}</option>)}
                  </Select>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
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
                    <li key={i} className="flex items-center justify-between gap-3 px-5 py-2.5 text-sm">
                      <button onClick={() => toggleChecklist(i, c.estado)} className="flex items-center gap-2 text-left">
                        <span className={`flex h-5 w-5 items-center justify-center rounded-md border text-[10px] ${c.estado === "listo" ? "border-teal bg-teal text-white" : "border-base"}`}>
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
                <CardHeader title="Cronograma interno sugerido" />
                <ul className="divide-y divide-[var(--border)]">
                  {sel.cronograma.map((c, i) => (
                    <li key={i} className="flex justify-between px-5 py-2 text-sm">
                      <span className="text-muted">{c.tarea}</span><span className="font-medium">{c.plazo}</span>
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
                    <div className="flex gap-2">
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
                        <summary className="cursor-pointer text-xs font-medium">{b.tipo} · v{b.version} · {b.fecha}</summary>
                        <pre className="text-muted mt-2 whitespace-pre-wrap text-[11px]">{b.contenido}</pre>
                      </details>
                    ))
                  )}
                  <Textarea
                    placeholder="Contenido para respuestas técnicas (usa información verificada de tu empresa)…"
                    value={comentario}
                    onChange={(e) => setComentario(e.target.value)}
                  />
                  <p className="text-muted text-[11px]">
                    Nota: LicitaIA nunca genera certificaciones, experiencia ni firmas. La presentación en SECOP es manual.
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
                  <div className="flex gap-2">
                    <Input value={comentario} onChange={(e) => setComentario(e.target.value)} placeholder="Añadir comentario…" />
                    <Button size="sm" onClick={enviarComentario}>Comentar</Button>
                  </div>
                </div>
              </Card>
            </>
          )}
          {msg ? <p className="text-xs text-teal">{msg}</p> : null}
        </div>
      </div>
    </div>
  );
}
