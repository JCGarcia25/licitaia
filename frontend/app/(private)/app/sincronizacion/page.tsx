"use client";
/* Sincronización SECOP: ingesta incremental y auditoría de corridas. */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Badge, Button, Card, CardHeader, Field, Input, Select, Spinner } from "@/components/ui";

type Run = {
  id: number; dataset: string; started_at: string; finished_at: string | null;
  pages: number; upserted: number; duplicates: number; errors: number; watermark: string | null;
};
type Process = { id: number; source_id: string; entidad: string | null; objeto: string | null; estado: string | null; modalidad: string | null; fecha_publicacion: string | null; url_oficial: string | null };

export default function Sincronizacion() {
  const [source, setSource] = useState("secop2_procesos");
  const [maxPages, setMaxPages] = useState("5");
  const [extraWhere, setExtraWhere] = useState("");
  const [corriendo, setCorriendo] = useState(false);
  const [resultado, setResultado] = useState<Record<string, unknown> | null>(null);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [procesos, setProcesos] = useState<Process[] | null>(null);
  const [datasetActivo, setDatasetActivo] = useState<string | null>(null);

  const cargarRuns = useCallback(async () => {
    setRuns(await api<Run[]>("/api/sync/runs"));
  }, []);

  async function verProcesos(dataset: string) {
    setDatasetActivo(dataset);
    setProcesos(null);
    try {
      const res = await api<{ items: Process[] }>(`/api/opportunities?source=${encodeURIComponent(dataset)}&solo_con_score=false&limit=50`);
      setProcesos(res.items);
    } catch {
      setProcesos([]);
    }
  }

  useEffect(() => { cargarRuns().catch(() => setRuns([])); }, [cargarRuns]);

  async function ejecutar() {
    setCorriendo(true);
    setResultado(null);
    try {
      const body: Record<string, unknown> = { source, max_pages: Number(maxPages) };
      if (extraWhere.trim()) body.extra_where = extraWhere.trim();
      const r = await api<Record<string, unknown>>("/api/sync/secop", { method: "POST", body: JSON.stringify(body) });
      setResultado(r);
      await cargarRuns();
    } catch (e) {
      setResultado({ error: e instanceof Error ? e.message : "Error" });
    } finally {
      setCorriendo(false);
    }
  }

  const FUENTES = [
    { v: "secop2_procesos", l: "SECOP II — Procesos de Contratación (p6dx-8zbt)" },
    { v: "secop2_contratos", l: "SECOP II — Contratos Electrónicos (jbjy-vk9h)" },
    { v: "secop1", l: "SECOP I (e985-4d7e)" },
  ];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Sincronización con SECOP</h1>
        <p className="text-muted text-sm">
          Ingesta incremental vía API Socrata de datos.gov.co. El agendamiento automático (cada 30 minutos) corre en el worker de Celery.
        </p>
      </div>

      <Card>
        <CardHeader title="Ejecutar ingesta manual" subtitle="Paginación de 1.000 registros con upsert idempotente (sin duplicados)" />
        <div className="grid gap-4 p-5 md:grid-cols-3">
          <Field label="Fuente">
            <Select value={source} onChange={(e) => setSource(e.target.value)}>
              {FUENTES.map((f) => <option key={f.v} value={f.v}>{f.l}</option>)}
            </Select>
          </Field>
          <Field label="Máximo de páginas" hint="Cada página trae hasta 1.000 registros.">
            <Input type="number" min={1} max={50} value={maxPages} onChange={(e) => setMaxPages(e.target.value)} />
          </Field>
          <Field label="Filtro SoQL adicional ($where, opcional)" hint="P. ej. departamento_entidad = 'Bogotá D.C.'">
            <Input value={extraWhere} onChange={(e) => setExtraWhere(e.target.value)} />
          </Field>
        </div>
        <div className="flex items-center gap-3 px-5 pb-5">
          <Button onClick={ejecutar} disabled={corriendo}>{corriendo ? "Sincronizando…" : "Ejecutar sincronización"}</Button>
          {resultado ? (
            <p className="text-muted text-xs">
              {"error" in resultado ? (
                <span className="text-red-600">{String(resultado.error)}</span>
              ) : (
                <>Nuevas: {String(resultado.upserted)} · Duplicadas actualizadas: {String(resultado.duplicates)} · Errores: {String(resultado.errors)}</>
              )}
            </p>
          ) : null}
        </div>
      </Card>

      <Card>
        <CardHeader title="Auditoría de sincronizaciones" subtitle="Últimas 20 corridas registradas" />
        {!runs ? (
          <Spinner />
        ) : runs.length === 0 ? (
          <p className="text-muted p-5 text-sm">Aún no hay corridas registradas.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-base text-muted">
                  <th className="px-5 py-2">ID</th><th className="px-3 py-2">Dataset</th><th className="px-3 py-2">Inicio</th>
                  <th className="px-3 py-2">Nuevas</th><th className="px-3 py-2">Duplicadas</th><th className="px-3 py-2">Errores</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id} className="border-b border-base">
                    <td className="px-5 py-2">{r.id}</td>
                    <td className="px-3 py-2"><button type="button" onClick={() => verProcesos(r.dataset)} title="Ver procesos de este dataset"><Badge tone="blue">{r.dataset}</Badge></button></td>
                    <td className="px-3 py-2">{new Date(r.started_at).toLocaleString("es-CO")}</td>
                    <td className="px-3 py-2 font-medium text-teal">{r.upserted}</td>
                    <td className="px-3 py-2">{r.duplicates}</td>
                    <td className={`px-3 py-2 ${r.errors ? "text-red-600 font-medium" : ""}`}>{r.errors}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {datasetActivo ? (
          <div className="border-t border-base p-5">
            <h3 className="text-sm font-semibold">Procesos del dataset {datasetActivo}</h3>
            {!procesos ? <Spinner label="Cargando procesos…" /> : procesos.length === 0 ? <p className="text-muted mt-2 text-sm">No hay procesos disponibles para este dataset.</p> : (
              <div className="mt-3 space-y-2">
                {procesos.map((p) => <div key={p.id} className="rounded-lg border border-base p-3 text-xs"><Link href={`/app/oportunidades/${p.id}`} className="font-semibold hover:text-teal">{p.objeto || "Proceso sin título"}</Link><p className="text-muted mt-1">{p.entidad || "Entidad no definida"} · {p.modalidad || "Modalidad no definida"} · {p.estado || "Estado no definido"}</p>{p.url_oficial ? <a href={p.url_oficial} target="_blank" rel="noreferrer" className="mt-1 inline-block text-teal hover:underline">Abrir expediente oficial en SECOP ↗</a> : <p className="text-muted mt-1">Sin enlace oficial disponible</p>}</div>)}
              </div>
            )}
          </div>
        ) : null}
      </Card>

      <Card className="p-5">
        <h3 className="text-sm font-semibold">Fuentes oficiales utilizadas</h3>
        <ul className="text-muted mt-2 space-y-1 text-xs">
          <li>• <a className="text-teal hover:underline" href="https://www.datos.gov.co/Estad-sticas-Nacionales/SECOP-II-Procesos-de-Contrataci-n/p6dx-8zbt" target="_blank" rel="noreferrer">SECOP II — Procesos de Contratación</a> (datos.gov.co, dataset p6dx-8zbt)</li>
          <li>• <a className="text-teal hover:underline" href="https://www.datos.gov.co/Estad-sticas-Nacionales/SECOP-II-Contratos-Electr-nicos/jbjy-vk9h" target="_blank" rel="noreferrer">SECOP II — Contratos Electrónicos</a> (dataset jbjy-vk9h, análisis histórico)</li>
          <li>• <a className="text-teal hover:underline" href="https://www.datos.gov.co/" target="_blank" rel="noreferrer">Datos Abiertos Colombia</a> y <a className="text-teal hover:underline" href="https://www.colombiacompra.gov.co/transparencia/datos-abiertos/conjuntos-de-datos-abiertos" target="_blank" rel="noreferrer">catálogo de Colombia Compra Eficiente</a></li>
        </ul>
        <p className="text-muted mt-3 text-[11px] leading-relaxed">
          Nota: el dataset de procesos no expone la fecha de cierre; los recordatorios usan la fecha analizada en pliegos o
          registrada por el usuario. La fuente oficial es siempre la referencia definitiva del estado del expediente.
        </p>
      </Card>
    </div>
  );
}
