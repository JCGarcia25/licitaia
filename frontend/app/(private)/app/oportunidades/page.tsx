"use client";
/* Oportunidades: filtros, búsqueda NLQ y triage. */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Badge, Button, Card, EmptyState, fmtCOP, fmtFecha, Input, MessageModal, Spinner, scoreTone, Select } from "@/components/ui";

type Reason = { factor: string; detalle: string; evidencia: string };
type Opp = {
  id: number; entidad: string; objeto: string; descripcion: string | null; valor: number | null;
  estado: string; departamento: string | null; modalidad: string | null; fecha_publicacion: string | null;
  score: number | null; triage: string; reasons: Reason[]; url_oficial: string | null; cancelled: boolean;
  documentos_publicos_disponibles?: number; url_consulta_secop?: string;
};
type SearchState = {
  q?: string; departamento?: string; municipio?: string; modalidad?: string;
  valorMin?: string; scoreMin?: string; triage?: string; soloScore?: boolean;
};
const DEPARTAMENTOS = ["Amazonas", "Antioquia", "Arauca", "Atlántico", "Bogotá D.C.", "Bolívar", "Boyacá", "Caldas", "Caquetá", "Casanare", "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca", "Huila", "La Guajira", "Magdalena", "Meta", "Nariño", "Norte de Santander", "Putumayo", "Quindío", "Risaralda", "Santander", "Sucre", "Tolima", "Valle del Cauca"];
const SEARCH_STORAGE_KEY = "mysecop:oportunidades:ultima-busqueda";

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
  // Buscar y filtrar es una capacidad común de Free y Pro. La puntuación es
  // opcional para que una cuenta nueva también vea resultados sincronizados.
  const [soloScore, setSoloScore] = useState(false);
  const [error, setError] = useState("");
  const [perfilRequerido, setPerfilRequerido] = useState(false);
  const [busquedaConPerfil, setBusquedaConPerfil] = useState(false);
  const [modal, setModal] = useState<{ title: string; message: string; tone: "error" | "info" } | null>(null);
  const [perfilAvisado, setPerfilAvisado] = useState(false);
  const [pagina, setPagina] = useState(1);
  const TAMANO_PAGINA = 25;
  const router = useRouter();

  const cargar = useCallback(async (nlq?: string, usarPerfil = false, paginaSolicitada = pagina, override?: SearchState) => {
    const estado = override || { q, departamento, municipio, modalidad, valorMin, scoreMin, triage, soloScore };
    const consulta = nlq ?? estado.q ?? "";
    const tieneFiltros = Boolean(estado.departamento || estado.municipio || estado.modalidad || estado.valorMin || estado.scoreMin || estado.triage);
    const esBusquedaManual = Boolean(consulta || (!usarPerfil && tieneFiltros));
    const aplicarPerfil = !esBusquedaManual && (usarPerfil || busquedaConPerfil);
    setBusquedaConPerfil(aplicarPerfil);
    setError("");
    const params = new URLSearchParams();
    if (consulta) params.set("q", consulta);
    if (estado.departamento) params.set("departamento", estado.departamento);
    if (estado.municipio) params.set("municipio", estado.municipio);
    if (estado.modalidad) params.set("modalidad", estado.modalidad);
    if (estado.valorMin) params.set("valor_min", estado.valorMin.replace(/[^\d]/g, ""));
    if (estado.scoreMin) params.set("score_min", estado.scoreMin);
    if (estado.triage) params.set("triage", estado.triage);
    params.set("solo_con_score", String(estado.soloScore ?? soloScore));
    if (esBusquedaManual) params.set("modo", "busqueda");
    params.set("limit", String(TAMANO_PAGINA));
    params.set("offset", String((paginaSolicitada - 1) * TAMANO_PAGINA));
    try {
      const searchBody = { q: consulta, departamento: estado.departamento || undefined, municipio: estado.municipio || undefined, modalidad: estado.modalidad || undefined, valor_min: estado.valorMin ? Number(estado.valorMin.replace(/[^\d]/g, "")) : undefined, score_min: estado.scoreMin ? Number(estado.scoreMin) : undefined, triage: estado.triage || undefined, solo_con_score: estado.soloScore ?? soloScore, limit: TAMANO_PAGINA, offset: (paginaSolicitada - 1) * TAMANO_PAGINA };
      let res = consulta
        ? await api<{ total: number; items: Opp[]; profile_required?: boolean }>("/api/search", { method: "POST", body: JSON.stringify(searchBody) })
        : await api<{ total: number; items: Opp[]; profile_required?: boolean }>(`/api/opportunities?${params.toString()}&profile_match=${aplicarPerfil}`);
      // En un ambiente recién sincronizado puede no haber puntuaciones aún.
      // La búsqueda textual sigue siendo útil: si el filtro de puntuadas no
      // encuentra nada, repetimos sin ese requisito y mostramos los procesos.
      if (consulta && res.total === 0 && searchBody.solo_con_score) {
        setSoloScore(false);
        res = await api<{ total: number; items: Opp[]; profile_required?: boolean }>("/api/search", { method: "POST", body: JSON.stringify({ ...searchBody, solo_con_score: false }) });
      }
      setPerfilRequerido(Boolean(res.profile_required));
      if (res.profile_required && !perfilAvisado) {
        setPerfilAvisado(true);
        setModal({ title: "Completa tu perfil para encontrar oportunidades", message: "Antes de mostrar procesos, necesitamos conocer las actividades, productos o servicios, ubicaciones y presupuesto de tu empresa. Así MySECOP podrá mostrarte coincidencias relevantes y evitar resultados que no correspondan a tu negocio.", tone: "info" });
      }
      setItems(res.items);
      setTotal(res.total);
      if (typeof window !== "undefined") {
        const url = new URL(window.location.href);
        params.set("pagina", String(paginaSolicitada));
        url.search = params.toString();
        window.history.replaceState(null, "", url.toString());
        if (esBusquedaManual) window.sessionStorage.setItem(SEARCH_STORAGE_KEY, params.toString());
        else window.sessionStorage.removeItem(SEARCH_STORAGE_KEY);
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : "No fue posible consultar las oportunidades.";
      if (message.toLowerCase().includes("exclusiva") || message.toLowerCase().includes("mysecop pro")) {
        setModal({ title: "Función disponible en MySECOP Pro", message: "Esta función es exclusiva de MySECOP Pro. Actualiza tu plan para continuar disfrutando el flujo completo.", tone: "info" });
        setError("");
      } else setError(message);
      setItems([]);
    }
  }, [q, departamento, municipio, modalidad, valorMin, scoreMin, triage, soloScore, busquedaConPerfil, pagina]);

  useEffect(() => {
    const saved = window.sessionStorage.getItem(SEARCH_STORAGE_KEY) || "";
    const params = new URLSearchParams(window.location.search || saved);
    const inicial = params.get("q") || "";
    const paginaInicial = Number(params.get("pagina") || "1");
    const estadoInicial: SearchState = {
      q: inicial,
      departamento: params.get("departamento") || "",
      municipio: params.get("municipio") || "",
      modalidad: params.get("modalidad") || "",
      valorMin: params.get("valor_min") || "",
      scoreMin: params.get("score_min") || "",
      triage: params.get("triage") || "",
      soloScore: params.has("solo_con_score") ? params.get("solo_con_score") === "true" : false,
    };
    setQ(estadoInicial.q || "");
    setDepartamento(estadoInicial.departamento || "");
    setMunicipio(estadoInicial.municipio || "");
    setModalidad(estadoInicial.modalidad || "");
    setValorMin(estadoInicial.valorMin || "");
    setScoreMin(estadoInicial.scoreMin || "");
    setTriage(estadoInicial.triage || "");
    setSoloScore(Boolean(estadoInicial.soloScore));
    setPagina(paginaInicial);
    if (inicial || params.get("modo") === "busqueda") {
      cargar(inicial, false, paginaInicial, estadoInicial);
    } else {
      cargar(undefined, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function aplicarTriage(id: number, valor: string) {
    await api(`/api/opportunities/${id}/triaje`, { method: "POST", body: JSON.stringify({ triage: valor }) });
    cargar(undefined, busquedaConPerfil);
  }

  function nuevaBusqueda() {
    setPagina(1);
    cargar(undefined, false, 1);
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
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && cargar()}
            placeholder='Búsqueda: texto libre o en lenguaje natural ("procesos abiertos de software en Bogotá superiores a 200 millones")' />
          <Button onClick={nuevaBusqueda} className="w-full shrink-0 whitespace-nowrap sm:w-auto sm:min-w-24">Buscar</Button>
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-6">
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
      {perfilRequerido ? <Card className="border-amber-300/60 bg-amber-50/70 dark:bg-amber-950/20"><p className="text-sm font-semibold">Completa primero el perfil de tu empresa</p><p className="text-muted mt-1 text-xs">Necesitamos tus actividades, productos o servicios y ubicación de interés para mostrar oportunidades relevantes.</p><Link href="/app/perfil" className="mt-3 inline-block text-sm font-semibold text-teal underline">Ir al perfil de empresa →</Link></Card> : null}

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
                  <div className="flex w-full flex-col gap-2 sm:w-auto sm:shrink-0">
                    <div className="flex flex-wrap gap-2">
                      <Link href={`/app/oportunidades/${o.id}`}><Button size="sm">Analizar</Button></Link>
                      {o.url_oficial ? <a href={o.url_oficial} target="_blank" rel="noopener,noreferrer"><Button size="sm" variant="outline">Ver en SECOP ↗</Button></a> : <Button size="sm" variant="outline" disabled>Expediente SECOP no disponible</Button>}
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" onClick={() => aplicarTriage(o.id, "descartada")}>Descartar</Button>
                    </div>
                    <Button size="sm" variant="outline" className="w-full" onClick={() => crearProyecto(o.id)}>Crear proyecto de propuesta</Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
          <div className="flex items-center justify-between border-t border-base pt-4 text-xs">
            <span className="text-muted">Página {pagina} de {Math.max(1, Math.ceil(total / TAMANO_PAGINA))}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={pagina <= 1} onClick={() => { const next = pagina - 1; setPagina(next); cargar(undefined, busquedaConPerfil, next); }}>Anterior</Button>
              <Button size="sm" variant="outline" disabled={pagina * TAMANO_PAGINA >= total} onClick={() => { const next = pagina + 1; setPagina(next); cargar(undefined, busquedaConPerfil, next); }}>Siguiente</Button>
            </div>
          </div>
        </>
      )}
      {modal ? <MessageModal {...modal} onClose={() => setModal(null)} actionLabel={modal.title.startsWith("Completa") ? "Completar perfil de empresa" : undefined} onAction={modal.title.startsWith("Completa") ? () => router.push("/app/perfil") : undefined} /> : null}
    </div>
  );
}
