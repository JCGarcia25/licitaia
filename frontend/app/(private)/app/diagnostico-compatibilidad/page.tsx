"use client";
import { buttonStyles } from "@/lib/button-styles";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Criterion = { criterion: string; state: string; subscore: number | null; weight: number; contribution: number | null; normalized_contribution: number | null; reason: string };
type Comparison = { opportunity_id: number; legacy_score: number | null; difference: number | null; v2: { compatibility_score: number | null; score_status: string; eligibility_status: string; evidence_coverage: number; sensitivity_interval: { lower: number | null; upper: number | null }; criteria: Criterion[]; warnings: string[]; model_version: string } };
type Run = { id: string; state: string; processed: number; total: number; results?: Comparison[] };
const base = "/api/internal/compatibility-v2";
const number = (v: number | null) => v === null ? "Sin determinar" : v.toFixed(1);

export default function Diagnostic() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<Run | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function refresh() { try { setRuns(await api<Run[]>(`${base}/runs`)); } catch { setError("Diagnóstico no disponible. Requiere autorización de administrador y habilitación en DEV."); } }
  useEffect(() => { void refresh(); }, []);
  async function execute(action: () => Promise<Run>) { setBusy(true); setError(""); try { setSelected(await action()); await refresh(); } catch (e) { setError(e instanceof Error ? e.message : "No fue posible consultar el diagnóstico"); } finally { setBusy(false); } }
  return <div className="space-y-5">
    <h1 className="text-2xl font-semibold">Diagnóstico privado de compatibilidad V2</h1>
    <p>Índice experimental de afinidad, no probabilidad de adjudicación. Los resultados no cambian recomendaciones ni alertas.</p>
    {error && <p role="alert">{error}</p>}
    {!error && <button className={buttonStyles({ variant: "outline" })} disabled={busy} onClick={() => void execute(() => api<Run>(`${base}/runs`, { method: "POST", body: JSON.stringify({ limit: 10 }) }))}>Evaluar muestra de hasta 10 oportunidades</button>}
    <div className="flex flex-wrap gap-3">{runs.map(r => <button key={r.id} disabled={busy} onClick={() => void execute(() => api<Run>(`${base}/runs/${r.id}`))}>{r.id.slice(0, 8)} · {r.state} · {r.processed}/{r.total}</button>)}</div>
    {selected && <section className="space-y-4"><p>Estado: {selected.state}. Muestra histórica privada, {selected.processed}/{selected.total}.</p>
      <button className={buttonStyles({ variant: "outline" })} disabled={busy} onClick={() => void execute(() => api<Run>(`${base}/runs/${selected.id}`))}>Actualizar resultado</button>
      {selected.results?.map(r => <article key={r.opportunity_id} className="space-y-3 rounded border p-4">
        <h2 className="font-semibold">Oportunidad {r.opportunity_id}</h2>
        <p>Heredado: {number(r.legacy_score)} · V2: {number(r.v2.compatibility_score)} · Diferencia: {number(r.difference)}</p>
        <p>{r.v2.score_status} · Elegibilidad: {r.v2.eligibility_status}</p>
        <p>Cobertura de información: {number(r.v2.evidence_coverage)}/100. Intervalo de sensibilidad: [{number(r.v2.sensitivity_interval.lower)}, {number(r.v2.sensitivity_interval.upper)}]. No es un intervalo de confianza estadística.</p>
        <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{["Criterio", "Estado", "Subíndice (0–1)", "Peso", "Contribución"].map(h => <th key={h} className="p-2">{h}</th>)}</tr></thead><tbody>{r.v2.criteria.map(c => <tr key={c.criterion}><td className="p-2">{c.criterion}<p>{c.reason}</p></td><td className="p-2">{c.state}</td><td className="p-2">{number(c.subscore)}</td><td className="p-2">{c.weight}</td><td className="p-2">{number(c.normalized_contribution)}</td></tr>)}</tbody></table></div>
        <ul>{r.v2.warnings.map(w => <li key={w}>{w}</li>)}</ul><p className="break-all text-xs">Versión: {r.v2.model_version}</p>
      </article>)}
    </section>}
  </div>;
}
