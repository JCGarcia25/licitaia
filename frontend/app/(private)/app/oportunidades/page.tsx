"use client";
/* Oportunidades: filtros, búsqueda NLQ y triage. */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Badge, Button, Card, EmptyState, fmtCOP, fmtFecha, Input, Spinner, scoreTone, Select } from "@/components/ui";

type Reason = { factor: string; detalle: string; evidencia: string };
type Opp = {
  id: number; entidad: string; objeto: string; descripcion: string | null; valor: number | null;
  estado: string; departamento: string | null; modalidad: string | null; fecha_publicacion: string | null;
  score: number | null; triage: string; reasons: Reason[]; url_oficial: string | null; cancelled: boolean;
  documentos_publicos_disponibles?: number; url_consulta_secop?: string;
};
const DEPARTAMENTOS = ["Amazonas", "Antioquia", "Arauca", "Atlántico", "Bogotá D.C.", "Bolívar", "Boyacá", "Caldas", "Caquetá", "Casanare", "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca", "Huila", "La Guajira", "Magdalena", "Meta", "Nariño", "Norte de Santander", "Putumayo", "Quindío", "Risaralda", "Santander", "Sucre", "Tolima", "Valle del Cauca"];

export default function Oportunidades() {
  const [items, setItems] = useState<Opp[] | null>(null);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [departamento, setDepartamento] = useState("");
  const [municipio, setMunicipio] = useState("");
  const [modalidad, setModalidad] = useState("");
  const [valorMin, setValorMin] = useState("");
  const [scoreMin, setScoreMin] = useState("");
  const [triage, setTriage] = useState("");
  const [soloScore, setSoloScore] = useState(true);
  const [error, setError] = useState("");
  const router = useRouter();

  const cargar = useCallback(async (nlq?: string) => {
    setError("");
    const params = new URLSearchParams();
    if (nlq || q) params.set("q", nlq || q);
    if (departamento) params.set("departamento", departamento);
    if (municipio) params.set("municipio", municipio);
    if (modalidad) params.set("modalidad", modalidad);
    if (valorMin) params.set("valor_min", valorMin.replace(/[^\d]/g, ""));
    if (scoreMin) params.set("score_min", scoreMin);
    if (triage) params.set("triage", triage);
    params.set("solo_con_score", String(soloScore));
    params.set("limit", "50");
    try {
      const res = q || nlq
        ? await api<{ total: number; items: Opp[] }>("/api/search", { method: "POST", body: JSON.stringify({ q: nlq || q, departamento: departamento || undefined, municipio: municipio || undefined, modalidad: modalidad || undefined, valor_min: valorMin ? Number(valorMin.replace(/[^\d]/g, "")) : undefined, solo_con_score: soloScore }) })
        : await api<{ total: number; items: Opp[] }>(`/api/opportunities?${params.toString()}`);
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
      setItems([]);
    }
  }, [q, departamento, municipio, modalidad, valorMin, scoreMin, triage, soloScore]);

  useEffect(() => {
    const inicial = new URLSearchParams(window.location.search).get("q");
    if (inicial) {
      setQ(inicial);
      cargar(inicial);
    } else {
      cargar();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function aplicarTriage(id: number, valor: string) {
    await api(`/api/opportunities/${id}/triaje`, { method: "POST", body: JSON.stringify({ triage: valor }) });
    cargar();
  }

  async function crearProyecto(id: number) {
    try {
      await api("/api/offer-projects", { method: "POST", body: JSON.stringify({ opportunity_id: id }) });
      await aplicarTriage(id, "proyecto");
      router.push("/app/ofertas");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error creando el proyecto");
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Oportunidades</h1>
        <p className="text-muted text-sm">Procesos de contratación pública puntuados para tu empresa por el Cazador de Oportunidades.</p>
      </div>

      {/* Filtros */}
      <Card className="space-y-3 p-4">
        <div className="flex gap-2">
          <Input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && cargar()}
            placeholder='Búsqueda: texto libre o en lenguaje natural ("procesos abiertos de software en Bogotá superiores a 200 millones")' />
          <Button onClick={() => cargar()}>Buscar</Button>
        </div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
          <Select value={departamento} onChange={(e) => { setDepartamento(e.target.value); setMunicipio(""); }}>
            <option value="">Toda Colombia</option>
            {DEPARTAMENTOS.map((d) => <option key={d} value={d}>{d}</option>)}
          </Select>
          <Input value={municipio} onChange={(e) => setMunicipio(e.target.value)} placeholder="Municipio" />
          <Select value={modalidad} onChange={(e) => setModalidad(e.target.value)}>
            <option value="">Toda modalidad</option>
            {["Licitación Pública", "Contratación Directa", "Contratación Mínima Cuantía", "Selección Abreviada", "Concurso de Méritos", "Régimen Especial", "Subasta"].map((mo) => (
              <option key={mo} value={mo}>{mo}</option>
            ))}
          </Select>
          <Input value={valorMin} onChange={(e) => setValorMin(e.target.value)} placeholder="Valor mínimo (COP)" />
          <Select value={scoreMin} onChange={(e) => setScoreMin(e.target.value)}>
            <option value="">Cualquier puntaje</option>
            <option value="70">≥ 70 (alta)</option>
            <option value="45">≥ 45 (media)</option>
          </Select>
          <Select value={triage} onChange={(e) => setTriage(e.target.value)}>
            <option value="">Todo el triage</option>
            <option value="detectada">Detectadas</option>
            <option value="guardada">Guardadas</option>
            <option value="proyecto">Proyectos</option>
            <option value="descartada">Descartadas</option>
          </Select>
        </div>
        <label className="text-muted flex items-center gap-2 text-xs">
          <input type="checkbox" checked={soloScore} onChange={(e) => setSoloScore(e.target.checked)} className="accent-teal" />
          Mostrar solo oportunidades ya puntuadas por el agente
        </label>
      </Card>

      {error ? <p className="text-xs text-red-600">{error}</p> : null}

      {!items ? (
        <Spinner label="Consultando oportunidades…" />
      ) : items.length === 0 ? (
        <Card><EmptyState title="Sin resultados" body="Ajusta los filtros o ejecuta una nueva sincronización en Sincronización SECOP." /></Card>
      ) : (
        <>
          <p className="text-muted text-xs">{total} oportunidad(es) encontrada(s)</p>
          <div className="space-y-3">
            {items.map((o) => (
              <Card key={o.id} className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={scoreTone(o.score)}>{o.score !== null ? `${Math.round(o.score)}% de compatibilidad estimada` : "sin puntuar"}</Badge>
                      {o.cancelled ? <Badge tone="red">Cancelado en la fuente</Badge> : <Badge tone="blue">{o.estado || "N/D"}</Badge>}
                      <Badge tone={o.documentos_publicos_disponibles ? "teal" : "amber"}>{o.documentos_publicos_disponibles ? `Pliegos disponibles (${o.documentos_publicos_disponibles})` : "Pliegos: consultar en SECOP"}</Badge>
                      {o.triage !== "detectada" ? <Badge tone={o.triage === "descartada" ? "gray" : "purple"}>{o.triage}</Badge> : null}
                    </div>
                    <Link href={`/app/oportunidades/${o.id}`} className="mt-2 block text-sm font-semibold hover:text-teal">
                      {o.objeto || "Proceso sin título"}
                    </Link>
                    <p className="text-muted mt-1 text-xs">{o.entidad} · {o.departamento || "N/D"} · {o.modalidad || "N/D"}</p>
                    <p className="text-muted mt-1 text-xs font-medium">
                      {fmtCOP(o.valor)} · Publicado: {fmtFecha(o.fecha_publicacion)}
                    </p>
                    {o.reasons?.length ? (
                      <ul className="mt-2 space-y-1">
                        {o.reasons.slice(0, 3).map((r, i) => (
                          <li key={i} className="text-muted text-[11px]"><span className="font-medium text-teal">{r.factor}:</span> {r.detalle}</li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                  <div className="flex flex-col gap-2">
                    <div className="flex gap-2">
                      <Link href={`/app/oportunidades/${o.id}`}><Button size="sm">Analizar</Button></Link>
                      <a href={o.url_oficial || o.url_consulta_secop || "https://www.datos.gov.co/"} target="_blank" rel="noreferrer"><Button size="sm" variant="outline">{o.url_oficial ? "Expediente SECOP ↗" : "Consultar SECOP ↗"}</Button></a>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => aplicarTriage(o.id, "guardada")}>Guardar</Button>
                      <Button size="sm" variant="ghost" onClick={() => aplicarTriage(o.id, "descartada")}>Descartar</Button>
                    </div>
                    <Button size="sm" variant="outline" onClick={() => crearProyecto(o.id)}>Crear proyecto de propuesta</Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
