"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Button, Card } from "@/components/ui";

type Coverage = { candidate_total: number; current_scores: number; pending_scores: number; stale_scores: number; failed_scores: number; excluded_total: number; coverage_percent: number | null };
type Job = { id: string; state: string; examined: number; coverage: Coverage };
const active = (job: Job | null) => !!job && ["PENDING", "RUNNING", "RETRY"].includes(job.state);
export function scoreLabel(state?: string) {
  return state === "STALE" ? "Pendiente de actualización" : state === "FAILED" ? "Cálculo pendiente de reintento" : state === "CALCULATING" ? "Calculando compatibilidad" : "Compatibilidad pendiente";
}

export function MatchProgress({ onProgress }: { onProgress?: () => void }) {
  const [job, setJob] = useState<Job | null>(null);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const callback = useRef(onProgress);
  callback.current = onProgress;
  const previous = useRef<string | undefined>(undefined);
  const epoch = useRef(0);
  const polling = useRef(false);
  const acting = useRef(false);
  useEffect(() => {
    let stopped = false;
    async function refresh() {
      if (polling.current || acting.current) return;
      polling.current = true;
      const version = epoch.current;
      try {
        const [latest, counts] = await Promise.all([api<Job | null>("/api/match-jobs/current"), api<Coverage>("/api/matches/coverage")]);
        if (stopped || version !== epoch.current) return;
        setJob(latest); setCoverage(counts); setError("");
        const signature = JSON.stringify([counts.current_scores, counts.stale_scores, counts.failed_scores, latest?.state]);
        if (previous.current !== undefined && previous.current !== signature) callback.current?.();
        previous.current = signature;
      } catch (e) {
        if (!stopped && version === epoch.current) setError(e instanceof Error ? e.message : "No se pudo consultar la cobertura.");
      } finally { if (version === epoch.current) polling.current = false; }
    }
    void refresh();
    const timer = setInterval(refresh, 5000);
    return () => { stopped = true; epoch.current += 1; polling.current = false; clearInterval(timer); };
  }, []);
  async function action(kind: "start" | "cancel" | "resume") {
    if (acting.current) return;
    acting.current = true; epoch.current += 1;
    setBusy(true); setError("");
    try {
      const result = await api<Job>(kind === "start" ? "/api/rescore" : `/api/match-jobs/${job?.id}/${kind}`, { method: "POST" });
      setJob(result); setCoverage(result.coverage);
      callback.current?.();
    } catch (e) { setError(e instanceof Error ? e.message : "No se pudo actualizar el cálculo."); }
    finally { acting.current = false; epoch.current += 1; polling.current = false; setBusy(false); }
  }
  return <Card className="space-y-2 p-4" aria-live="polite">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-sm font-semibold">Cobertura del Cazador</p>
      {active(job)
        ? <Button size="sm" variant="outline" disabled={busy} onClick={() => action("cancel")}>Cancelar cálculo</Button>
        : <Button size="sm" variant="outline" disabled={busy} onClick={() => action(job?.state === "FAILED" ? "resume" : "start")}>{job?.state === "FAILED" ? "Reintentar" : "Actualizar compatibilidad"}</Button>}
    </div>
    {coverage && <>
      <p className="text-sm">{coverage.current_scores.toLocaleString()} de {coverage.candidate_total.toLocaleString()} candidatas con puntuación vigente · {coverage.coverage_percent === null ? "Sin oportunidades candidatas" : `${coverage.coverage_percent}% de cobertura`}</p>
      <p className="text-xs text-muted">{coverage.pending_scores} pendientes · {coverage.stale_scores} desactualizadas · {coverage.failed_scores} con error · {coverage.excluded_total} excluidas. La cobertura mide el avance, no la compatibilidad.</p>
    </>}
    {active(job) && <p className="text-xs text-muted">{job?.state === "RUNNING" ? "Calculando compatibilidad por lotes…" : "Cálculo en cola; los resultados se actualizarán progresivamente."}</p>}
    {error && <p className="text-sm text-red-600">{error}</p>}
  </Card>;
}
