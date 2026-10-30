"use client";
/* Detalle de oportunidad: Agentes 2 (pliegos) y 3 (viabilidad). */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Badge, Button, Card, CardHeader, EmptyState, fmtCOP, fmtFecha, Input, scoreTone, Select, Spinner } from "@/components/ui";

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
  const [archivo, setArchivo] = useState<File | null>(null);
  const [msg, setMsg] = useState("");
  const [cargando, setCargando] = useState("");
  const [visor, setVisor] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    const data = await api<Opp>(`/api/opportunities/${id}`);
    setOpp(data);
    const d = await api<{ id: number; filename: string }[]>(`/api/documents?opportunity_id=${id}`);
    setDocs(d);
  }, [id]);

  useEffect(() => { cargar().catch((e) => setMsg(e.message)); }, [cargar]);

  async function subir() {
    if (!archivo) return;
    setCargando("subir");
    setMsg("");
    try {
      const form = new FormData();
      form.append("file", archivo);
      form.append("opportunity_id", String(id));
      await api("/api/documents", { method: "POST", body: form });
      setArchivo(null);
      await cargar();
      setMsg("Documento cargado correctamente.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Error subiendo el documento");
    } finally {
      setCargando("");
    }
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
    try {
      await api(`/api/opportunities/${id}/analyze`, { method: "POST" });
      await cargar();
      setMsg("Análisis de pliegos generado. Recuerda: es orientativo y requiere validación humana.");
    } catch (e) {
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
        <div><p className="text-muted text-xs">Estado</p><p className="mt-1 font-semibold">{opp.estado || "N/D"}{opp.source_id ? ` · ${opp.source_id}` : ""}</p></div>
        <div><p className="text-muted text-xs">Fecha de publicación (fuente)</p><p className="mt-1 font-semibold">{fmtFecha(opp.fecha_publicacion)}</p></div>
        <div><p className="text-muted text-xs">Departamento</p><p className="mt-1 font-semibold">{opp.departamento || "N/D"}</p></div>
        <div><p className="text-muted text-xs">Modalidad</p><p className="mt-1 font-semibold">{opp.modalidad || "N/D"}</p></div>
        <div>
          <p className="text-muted text-xs">Expediente original</p>
          {opp.url_oficial ? (
            <a href={opp.url_oficial} target="_blank" rel="noreferrer" className="mt-1 inline-block text-sm font-semibold text-teal hover:underline">
              Ver en SECOP ↗
            </a>
          ) : <a href={opp.url_consulta_secop || "https://www.datos.gov.co/"} target="_blank" rel="noreferrer" className="mt-1 inline-block text-sm font-semibold text-teal hover:underline">Consultar proceso en SECOP ↗</a>}
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
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={importarDocumentos} disabled={cargando === "importar"}>{cargando === "importar" ? "Importando…" : "Importar documentos públicos"}</Button>
            <Input type="file" accept=".pdf,.docx,.xlsx" onChange={(e) => setArchivo(e.target.files?.[0] || null)} className="max-w-sm py-1.5" />
            <Button size="sm" variant="outline" onClick={subir} disabled={!archivo || cargando === "subir"}>Subir documento</Button>
          </div>
          {docs.length ? (
            <ul className="text-muted space-y-1 text-xs">
              {docs.map((d) => <li key={d.id} className="flex items-center justify-between gap-2"><span>📎 {d.filename}</span><Button size="sm" variant="ghost" onClick={() => abrirDocumento(d)}>Ver</Button></li>)}
            </ul>
          ) : (
            <p className={`rounded-lg border p-3 text-xs ${opp.documentos_publicos_disponibles ? "border-teal/30 text-teal" : "border-amber-500/30 text-amber-700"}`}>{opp.documentos_publicos_disponibles ? `Pliegos disponibles para importar: ${opp.documentos_publicos_disponibles}.` : "Pliegos no expuestos para descarga automática: consultar en SECOP."} Pulsa «Importar documentos públicos» para comprobarlos; si SECOP requiere sesión, descarga el pliego desde el expediente y súbelo aquí.</p>
          )}
          {msg && !opp.analysis ? <p className="rounded-lg bg-teal/10 p-3 text-xs text-teal">{msg}</p> : null}
          {visor ? <div className="rounded-lg border border-base p-2"><div className="mb-2 flex justify-end"><Button size="sm" variant="ghost" onClick={() => { URL.revokeObjectURL(visor); setVisor(null); }}>Cerrar visor</Button></div><iframe title="Visor de documento" src={visor} className="h-[620px] w-full rounded" /></div> : null}

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
          action={<Button size="sm" onClick={evaluar} disabled={cargando === "viabilidad"}>{cargando === "viabilidad" ? "Evaluando…" : "Evaluar viabilidad"}</Button>}
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

      {msg ? <p className="text-muted text-xs">{msg}</p> : null}
      <div className="flex gap-2">
        <Button variant="outline" onClick={crearProyecto}>Crear proyecto de propuesta (Agente 4)</Button>
      </div>
    </div>
  );
}
