"use client";
/* Detalle de oportunidad: Agentes 2 (pliegos) y 3 (viabilidad). */
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Badge, Button, Card, CardHeader, EmptyState, fmtCOP, fmtFecha, scoreTone, Select, Spinner } from "@/components/ui";

type Reason = { factor: string; detalle: string; evidencia: string };
type Requisito = {
  descripcion: string; tipo: string; estado: string; evidencia: string;
  documento: string; referencia: string; observaciones: string; nivel_confianza: string; es_excluyente: boolean;
};
type Opp = {
  id: number; source: string; source_id: string; entidad: string; objeto: string; descripcion: string | null;
  modalidad: string | null; valor: number | null; estado: string; departamento: string | null;
  fecha_publicacion: string | null; updated_at?: string | null; fecha_cierre?: string | null; url_oficial: string | null; score: number | null; triage: string;
  reasons: Reason[]; analysis: { id: number; resumen: Record<string, any>; requisitos: Requisito[] } | null;
  documentos_publicos_disponibles?: number; url_consulta_secop?: string;
};
type Viab = {
  global_score: number; factors: Record<string, { score: number; peso: number; detalle: string }>;
  critical_failures: string[]; fortalezas: string[]; debilidades: string[]; docs_faltantes: string[];
  riesgos: string[]; costo_estimado: Record<string, unknown>; recommendation: string; disclaimer: string;
};

const ESTADO_TONE: Record<string, "green" | "red" | "amber" | "gray"> = {
  "Cumple": "green", "No cumple": "red", "Por verificar": "amber", "Información insuficiente": "gray",
};

export default function DetalleOportunidad() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [opp, setOpp] = useState<Opp | null>(null);
  const [viab, setViab] = useState<Viab | null>(null);
  const [docs, setDocs] = useState<{ id: number; filename: string }[]>([]);
  const [docsSeleccionados, setDocsSeleccionados] = useState<number[]>([]);
  const [archivos, setArchivos] = useState<File[]>([]);
  const [msg, setMsg] = useState("");
  const [cargando, setCargando] = useState("");
  const [visor, setVisor] = useState<string | null>(null);
  const [analisisValidado, setAnalisisValidado] = useState(false);
  const [validacionDocumentos, setValidacionDocumentos] = useState<{ documento: string; pertenece_al_proceso: boolean }[]>([]);
  const [arrastrando, setArrastrando] = useState(false);
  const archivoInput = useRef<HTMLInputElement | null>(null);

  const cargar = useCallback(async () => {
    const data = await api<Opp>(`/api/opportunities/${id}`);
    setOpp(data);
    const d = await api<{ id: number; filename: string }[]>(`/api/documents?opportunity_id=${id}`);
    setDocs(d);
    setDocsSeleccionados((seleccionados) => seleccionados.filter((docId) => d.some((doc) => doc.id === docId)));
  }, [id]);

  useEffect(() => { cargar().catch((e) => setMsg(e.message)); }, [cargar]);

  async function subir() {
    if (!archivos.length) return;
    setCargando("subir");
    setMsg("");
    try {
      for (const archivo of archivos) {
        const form = new FormData();
        form.append("file", archivo);
        form.append("opportunity_id", String(id));
        await api("/api/documents", { method: "POST", body: form });
      }
      const total = archivos.length;
      setArchivos([]);
      await cargar();
      setMsg(`${total} documento(s) cargado(s) correctamente.`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Error subiendo el documento");
    } finally {
      setCargando("");
    }
  }

  function aceptarArchivos(seleccionados: FileList | File[] | undefined) {
    if (!seleccionados) return;
    const validos: File[] = [];
    const errores: string[] = [];
    Array.from(seleccionados).forEach((file) => {
      if (!/\.(pdf|docx|xlsx)$/i.test(file.name)) errores.push(`${file.name}: formato no soportado`);
      else if (file.size > 25 * 1024 * 1024) errores.push(`${file.name}: supera 25 MB`);
      else validos.push(file);
    });
    setArchivos((actuales) => {
      const nombres = new Set(actuales.map((file) => file.name));
      return [...actuales, ...validos.filter((file) => !nombres.has(file.name))];
    });
    setMsg(errores.length ? errores.join(". ") : "");
  }

  async function eliminarDocumento(documentId: number) {
    if (!window.confirm("¿Eliminar este documento? Esta acción no se puede deshacer.")) return;
    try {
      await api(`/api/documents/${documentId}`, { method: "DELETE" });
      setDocsSeleccionados((seleccionados) => seleccionados.filter((docId) => docId !== documentId));
      await cargar();
      setMsg("Documento eliminado.");
    } catch (e) { setMsg(e instanceof Error ? e.message : "No fue posible eliminar el documento"); }
  }

  async function eliminarDocumentosSeleccionados() {
    if (!docsSeleccionados.length) return;
    if (!window.confirm(`¿Eliminar ${docsSeleccionados.length} documento(s)? Esta acción no se puede deshacer.`)) return;
    setCargando("eliminar");
    try {
      await Promise.all(docsSeleccionados.map((docId) => api(`/api/documents/${docId}`, { method: "DELETE" })));
      const total = docsSeleccionados.length;
      setDocsSeleccionados([]);
      await cargar();
      setMsg(`${total} documento(s) eliminado(s).`);
    } catch (e) { setMsg(e instanceof Error ? e.message : "No fue posible eliminar los documentos seleccionados"); }
    finally { setCargando(""); }
  }

  async function abrirDocumento(doc: { id: number; filename: string; mime_type?: string }) {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/documents/${doc.id}/content`, { headers: { Authorization: `Bearer ${localStorage.getItem("licitaia_token") || ""}` } });
      if (!response.ok) throw new Error("No fue posible abrir el documento");
      const blob = await response.blob();
      setVisor(URL.createObjectURL(blob));
    } catch (e) { setMsg(e instanceof Error ? e.message : "Error abriendo documento"); }
  }

  async function analizar() {
    setCargando("analizar");
    setMsg("");
    setAnalisisValidado(false);
    setValidacionDocumentos([]);
    try {
      const resultado = await api<{ documentos?: { documento: string; pertenece_al_proceso: boolean }[] }>(`/api/opportunities/${id}/analyze`, { method: "POST" });
      setValidacionDocumentos(resultado.documentos || []);
      await cargar();
      setAnalisisValidado(true);
      setMsg("Análisis de pliegos generado. Recuerda: es orientativo y requiere validación humana.");
    } catch (e) {
      const payload = (e as Error & { payload?: { detail?: { message?: string; documentos?: { documento: string; pertenece_al_proceso: boolean }[] } } }).payload;
      if (payload?.detail?.documentos) setValidacionDocumentos(payload.detail.documentos);
      if (payload?.detail?.message) setMsg(payload.detail.message);
      setMsg(e instanceof Error ? e.message : "Error en el análisis");
    } finally {
      setCargando("");
    }
  }

  async function importarDocumentos() {
    setCargando("importar"); setMsg("");
    try {
      const r = await api<{ importados: unknown[]; omitidos: unknown[] }>(`/api/documents/import-public/${id}`, { method: "POST" });
      await cargar();
      setMsg(`${r.importados.length} documento(s) público(s) importado(s). ${r.omitidos.length} omitido(s) por requerir acceso o carga manual.`);
    } catch (e) { setMsg(e instanceof Error ? e.message : "No fue posible importar documentos"); }
    finally { setCargando(""); }
  }

  async function evaluar() {
    setCargando("viabilidad");
    setMsg("");
    try {
      const r = await api<Viab>(`/api/opportunities/${id}/viability`, { method: "POST", body: "{}" });
      setViab(r);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Error evaluando viabilidad");
    } finally {
      setCargando("");
    }
  }

  async function crearProyecto() {
    try {
      await api("/api/offer-projects", { method: "POST", body: JSON.stringify({ opportunity_id: Number(id) }) });
      setMsg("Proyecto de oferta creado. Verlo en Ofertas.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Error");
    }
  }

  if (!opp) return <Spinner />;
  const resumen = opp.analysis?.resumen || {};

  return (
    <div className="space-y-5">
      <div>
        <Link href="/app/oportunidades" className="text-muted text-xs hover:text-teal">← Volver a oportunidades</Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <h1 className="max-w-3xl text-xl font-bold tracking-tight">{opp.objeto || "Proceso"}</h1>
          <Badge tone={scoreTone(opp.score)}>{opp.score !== null ? `${Math.round(opp.score)}% de compatibilidad` : "sin puntuar"}</Badge>
        </div>
        <p className="text-muted mt-1 text-sm">{opp.entidad}</p>
      </div>

      {/* Datos del proceso */}
      <Card className="grid gap-4 p-5 md:grid-cols-3">
        <div><p className="text-muted text-xs">Valor estimado</p><p className="mt-1 font-semibold">{fmtCOP(opp.valor)}</p></div>
        <div><p className="text-muted text-xs">Estado · Nº de proceso SECOP</p><p className="mt-1 font-semibold">{opp.estado || "N/D"}{opp.source_id && !opp.source_id.includes("DEMO") ? ` · ${opp.source_id}` : " · Número oficial no disponible"}</p></div>
        <div><p className="text-muted text-xs">Fecha de publicación (fuente)</p><p className="mt-1 font-semibold">{fmtFecha(opp.fecha_publicacion)}</p></div>
        <div><p className="text-muted text-xs">Departamento</p><p className="mt-1 font-semibold">{opp.departamento || "N/D"}</p></div>
        <div><p className="text-muted text-xs">Modalidad</p><p className="mt-1 font-semibold">{opp.modalidad || "N/D"}</p></div>
        <div>
          <p className="text-muted text-xs">Expediente original</p>
          {opp.url_oficial ? (
            <a href={opp.url_oficial} target="_blank" rel="noreferrer" className="mt-1 inline-block text-sm font-semibold text-teal hover:underline">
              Ver en SECOP ↗
            </a>
          ) : <span className="text-muted mt-1 inline-block text-xs">Enlace directo al expediente SECOP no disponible para este proceso.</span>}
        </div>
        {opp.descripcion ? <div className="md:col-span-3"><p className="text-muted text-xs">Descripción</p><p className="mt-1 text-sm">{opp.descripcion}</p></div> : null}
      </Card>

      <Card>
        <CardHeader title="Proceso y cronograma" subtitle="Fechas disponibles en la fuente oficial" />
        <div className="grid gap-3 p-5 text-sm md:grid-cols-3">
          <div><p className="text-muted text-xs">Publicación</p><p className="mt-1 font-semibold">{fmtFecha(opp.fecha_publicacion)}</p></div>
          <div><p className="text-muted text-xs">Última actualización</p><p className="mt-1 font-semibold">{fmtFecha(opp.updated_at)}</p></div>
          <div><p className="text-muted text-xs">Cierre de ofertas</p><p className="mt-1 font-semibold">{opp.fecha_cierre ? fmtFecha(opp.fecha_cierre) : "No expuesto por SECOP"}</p></div>
        </div>
      </Card>

      {/* Razones de coincidencia */}
      {opp.reasons?.length ? (
        <Card>
          <CardHeader title="Por qué coincide con tu empresa" subtitle="Razones verificables del registro oficial" />
          <ul className="divide-y divide-[var(--border)]">
            {opp.reasons.map((r, i) => (
              <li key={i} className="px-5 py-3 text-sm">
                <span className="font-medium text-teal">{r.factor}</span>
                <p className="text-muted mt-0.5 text-xs">{r.detalle}</p>
                {r.evidencia ? <p className="text-muted mt-1 text-[11px] italic">Evidencia: {r.evidencia}</p> : null}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {/* Agente 2: documentos y análisis */}
      <Card>
        <CardHeader
          title="Agente 2 · Analista de Pliegos"
          subtitle="Sube el pliego o anexos (PDF, DOCX, XLSX) y genera la matriz de requisitos con citas"
          action={<Button size="sm" onClick={analizar} disabled={cargando === "analizar"}>{cargando === "analizar" ? "Analizando…" : "Analizar documentos"}</Button>}
        />
        <div className="space-y-4 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" onClick={importarDocumentos} disabled={cargando === "importar"}>{cargando === "importar" ? "Importando…" : "Importar documentos públicos"}</Button>
            <input ref={archivoInput} type="file" multiple accept=".pdf,.docx,.xlsx" className="hidden" onChange={(e) => aceptarArchivos(e.target.files || undefined)} />
            <div
              className={`min-w-[280px] flex-1 rounded-xl border-2 border-dashed px-4 py-4 text-center text-xs transition ${arrastrando ? "border-teal bg-teal/10 text-teal" : "border-base text-muted hover:border-teal/60"}`}
              onDragOver={(e) => { e.preventDefault(); setArrastrando(true); }}
              onDragLeave={() => setArrastrando(false)}
              onDrop={(e) => { e.preventDefault(); setArrastrando(false); aceptarArchivos(e.dataTransfer.files); }}
            >
              <p className="font-medium">{archivos.length ? `📎 ${archivos.length} archivo(s) seleccionado(s)` : "Arrastra aquí los pliegos o anexos"}</p>
              <p className="mt-1">PDF, DOCX o XLSX · máximo 25 MB</p>
              <Button size="sm" variant="ghost" onClick={() => archivoInput.current?.click()} className="mt-2">Buscar archivo</Button>
            </div>
            <Button size="sm" variant="outline" onClick={subir} disabled={!archivos.length || cargando === "subir"}>{cargando === "subir" ? "Subiendo…" : `Subir ${archivos.length || ""} documento(s)`}</Button>
          </div>
          {archivos.length ? <ul className="text-muted flex flex-wrap gap-2 text-xs">{archivos.map((file, index) => <li key={`${file.name}-${index}`} className="rounded-full border border-base px-2 py-1">{file.name} <button type="button" className="ml-1 text-red-400" onClick={() => setArchivos((actuales) => actuales.filter((_, i) => i !== index))} aria-label={`Quitar ${file.name}`}>×</button></li>)}</ul> : null}
          {docs.length ? (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-base pb-2 text-xs">
                <label className="text-muted flex items-center gap-2"><input type="checkbox" checked={docsSeleccionados.length === docs.length} onChange={(e) => setDocsSeleccionados(e.target.checked ? docs.map((d) => d.id) : [])} /> Seleccionar todos</label>
                <Button size="sm" variant="outline" disabled={!docsSeleccionados.length || cargando === "eliminar"} onClick={eliminarDocumentosSeleccionados}>{cargando === "eliminar" ? "Eliminando…" : `Eliminar seleccionados (${docsSeleccionados.length})`}</Button>
              </div>
              <ul className="text-muted space-y-1 text-xs">
                {docs.map((d) => <li key={d.id} className="flex items-center justify-between gap-2"><label className="flex min-w-0 items-center gap-2"><input type="checkbox" checked={docsSeleccionados.includes(d.id)} onChange={(e) => setDocsSeleccionados((seleccionados) => e.target.checked ? [...seleccionados, d.id] : seleccionados.filter((docId) => docId !== d.id))} /><span className="truncate">📎 {d.filename}</span></label><span className="flex shrink-0 gap-1"><Button size="sm" variant="ghost" onClick={() => abrirDocumento(d)}>Ver</Button><Button size="sm" variant="ghost" onClick={() => eliminarDocumento(d.id)}>Eliminar</Button></span></li>)}
              </ul>
            </div>
          ) : (
            <p className={`rounded-lg border p-3 text-xs ${opp.documentos_publicos_disponibles ? "border-teal/30 text-teal" : "border-amber-500/30 text-amber-700"}`}>{opp.documentos_publicos_disponibles ? `Pliegos disponibles para importar: ${opp.documentos_publicos_disponibles}.` : "Pliegos no expuestos para descarga automática: consultar en SECOP."} Pulsa «Importar documentos públicos» para comprobarlos; si SECOP requiere sesión, descarga el pliego desde el expediente y súbelo aquí.</p>
          )}
          {visor ? <div className="rounded-lg border border-base p-2"><div className="mb-2 flex justify-end"><Button size="sm" variant="ghost" onClick={() => { URL.revokeObjectURL(visor); setVisor(null); }}>Cerrar visor</Button></div><iframe title="Visor de documento" src={visor} className="h-[620px] w-full rounded" /></div> : null}

          {validacionDocumentos.length ? <div className="rounded-lg border border-base p-3 text-xs"><p className="font-medium">Validación de documentos</p><ul className="text-muted mt-2 space-y-1">{validacionDocumentos.map((d) => <li key={d.documento}><span className={d.pertenece_al_proceso ? "text-emerald-500" : "text-red-400"}>{d.pertenece_al_proceso ? "✓" : "!"}</span> {d.documento}: {d.pertenece_al_proceso ? "corresponde al proceso seleccionado" : "no parece corresponder al proceso seleccionado"}</li>)}</ul></div> : null}

          {opp.analysis ? (
            <div className="space-y-4">
              {/* Resumen ejecutivo */}
              <div className="grid gap-3 rounded-lg border border-base p-4 md:grid-cols-2">
                {Object.entries(resumen).filter(([k]) => k !== "descargo" && k !== "total_requisitos" && k !== "requisitos_excluyentes" && k !== "generado" && k !== "error" && k !== "sugerencia").map(([clave, v]) => (
                  <div key={clave}>
                    <p className="text-muted text-[11px] capitalize">{clave.replace(/_/g, " ")}</p>
                    <p className="mt-0.5 text-sm font-medium">{v?.valor || "Información insuficiente"}</p>
                    {v?.referencia ? (
                      <p className="text-muted text-[11px]">
                        {v.documento} · {v.referencia} · confianza {v.confianza}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>

              {/* Matriz de requisitos */}
              {opp.analysis.requisitos.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-base text-muted">
                        <th className="py-2 pr-3">Requisito</th>
                        <th className="py-2 pr-3">Tipo</th>
                        <th className="py-2 pr-3">Estado</th>
                        <th className="py-2 pr-3">Referencia</th>
                        <th className="py-2">Confianza</th>
                      </tr>
                    </thead>
                    <tbody>
                      {opp.analysis.requisitos.slice(0, 30).map((r, i) => (
                        <tr key={i} className="border-b border-base align-top">
                          <td className="py-2 pr-3">
                            <p className="max-w-md">{r.descripcion}</p>
                            {r.observaciones ? <p className="mt-0.5 text-[11px] text-teal">{r.observaciones}</p> : null}
                          </td>
                          <td className="py-2 pr-3"><Badge tone="blue">{r.tipo}</Badge></td>
                          <td className="py-2 pr-3"><Badge tone={ESTADO_TONE[r.estado] || "gray"}>{r.estado}</Badge></td>
                          <td className="text-muted py-2 pr-3">{r.documento} · {r.referencia}</td>
                          <td className="py-2">{r.nivel_confianza}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              <p className="text-muted text-[11px] leading-relaxed">{String(resumen.descargo || "Resultado orientativo: requiere validación humana.")}</p>
            </div>
          ) : (
            <EmptyState title="Sin análisis generado" body="Carga un documento y presiona «Analizar documentos»." />
          )}
        </div>
      </Card>

      {/* Agente 3: viabilidad */}
      <Card>
        <CardHeader
          title="Agente 3 · Evaluador de Viabilidad"
          subtitle="¿Vale la pena participar? Pesos configurables, distintos de toda probabilidad de adjudicación"
          action={<Button size="sm" onClick={evaluar} disabled={!analisisValidado || cargando === "viabilidad"}>{cargando === "viabilidad" ? "Evaluando…" : "Evaluar viabilidad"}</Button>}
        />
        <div className="space-y-4 p-5">
          {viab ? (
            <>
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-full border-4 border-teal text-lg font-extrabold">
                  {Math.round(viab.global_score)}
                </div>
                <Badge tone={viab.recommendation === "participar" ? "green" : viab.recommendation === "revisar" ? "amber" : "red"}>
                  Recomendación: {viab.recommendation}
                </Badge>
                {viab.costo_estimado?.estimado_cop ? (
                  <span className="text-muted text-xs">
                    Costo estimado de preparar la oferta: {fmtCOP(Number(viab.costo_estimado.estimado_cop))} ({String(viab.costo_estimado.horas_estimadas)} h)
                  </span>
                ) : null}
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  {Object.entries(viab.factors).map(([k, f]) => (
                    <div key={k}>
                      <div className="flex justify-between text-xs">
                        <span className="text-muted">{f.detalle} <span className="text-[10px]">(peso {f.peso}%)</span></span>
                        <span className="font-medium">{Math.round(f.score)}</span>
                      </div>
                      <div className="mt-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800">
                        <div className="h-full rounded-full bg-teal" style={{ width: `${f.score}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="space-y-2 text-xs">
                  {viab.fortalezas.length ? <p><span className="font-medium text-emerald-600">Fortalezas:</span> <span className="text-muted">{viab.fortalezas.join(" · ")}</span></p> : null}
                  {viab.debilidades.length ? <p><span className="font-medium text-amber-600">Debilidades:</span> <span className="text-muted">{viab.debilidades.join(" · ")}</span></p> : null}
                  {viab.critical_failures.length ? <p><span className="font-medium text-red-600">Críticos sin evidencia:</span> <span className="text-muted">{viab.critical_failures.length} requisito(s)</span></p> : null}
                  {viab.riesgos.map((r, i) => <p key={i} className="text-muted">⚠ {r}</p>)}
                </div>
              </div>
              <p className="text-muted text-[11px] leading-relaxed">{viab.disclaimer}</p>
            </>
          ) : (
            <EmptyState title="Sin evaluación" body="Genera primero el análisis de pliegos y presiona «Evaluar viabilidad»." />
          )}
        </div>
      </Card>

      {msg ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4" role="dialog" aria-modal="true" aria-label="Mensaje del sistema">
          <div className="w-full max-w-md rounded-2xl border border-base bg-[var(--surface)] p-6 text-center shadow-2xl">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-teal/15 text-3xl text-teal">✓</div>
            <h2 className="text-lg font-semibold">Información del proceso</h2>
            <p className="text-muted mt-2 text-sm">{msg}</p>
            <Button className="mt-5 w-full" onClick={() => setMsg("")}>Continuar en MySECOP</Button>
          </div>
        </div>
      ) : null}
      <div className="flex gap-2">
        <Button variant="outline" onClick={crearProyecto}>Crear proyecto de propuesta (Agente 4)</Button>
      </div>
    </div>
  );
}
