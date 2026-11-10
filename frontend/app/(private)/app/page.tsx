"use client";
/* Dashboard ejecutivo: métricas, tendencia y top oportunidades. */
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Badge, Button, Card, CardHeader, EmptyState, fmtCOP, Input, Spinner, scoreTone } from "@/components/ui";

type Metrics = {
  oportunidades_detectadas: number;
  procesos_nuevos_base: number;
  proximos_a_cerrar: number;
  alta_compatibilidad: number;
  umbral_compatibilidad: number;
  valor_agregado_cop: number;
  guardadas: number;
  descartadas: number;
  proyectos_propuesta: number;
  documentos_pendientes: number;
  ofertas_activas: number;
  alertas_no_leidas: number;
  tendencia_mensual: { mes: string; total: number }[];
};

type Opp = {
  id: number; entidad: string; objeto: string; valor: number | null; estado: string;
  departamento: string | null; score: number | null; url_oficial: string | null;
};
type AlertPrefs = { email_enabled: boolean; high_score_threshold: number; close_days: number[]; digest_hour: number };
const FRASES_CALMA = [
  "La calma también es una forma de avanzar.",
  "Cada paso claro encuentra su propio camino.",
  "En lo simple también habita lo esencial.",
  "Respira. Lo importante se construye con paciencia.",
  "La imperfección de hoy puede ser la semilla de mañana.",
];

export default function Dashboard() {
  const [m, setM] = useState<Metrics | null>(null);
  const [top, setTop] = useState<Opp[]>([]);
  const [consulta, setConsulta] = useState("");
  const [umbral, setUmbral] = useState(50);
  const [diasNuevos, setDiasNuevos] = useState(7);
  const [prefs, setPrefs] = useState<AlertPrefs | null>(null);
  const [guardandoCriterios, setGuardandoCriterios] = useState(false);
  const [cargandoTop, setCargandoTop] = useState(true);
  const [fraseCalma] = useState(() => FRASES_CALMA[Math.floor(Math.random() * FRASES_CALMA.length)]);
  const router = useRouter();

  async function cargar(umbralActual = umbral, diasActuales = diasNuevos) {
    setCargandoTop(true);
    try {
    const metrics = await api<Metrics>(`/api/dashboard/metrics?compatibility_threshold=${umbralActual}&new_days=${diasActuales}`);
    setM(metrics);
    // Mantener el mismo criterio que la vista Oportunidades: solo procesos
    // compatibles con el perfil y con una puntuación mínima significativa.
    let res = await api<{ items: Opp[] }>(`/api/opportunities?limit=50&score_min=${umbralActual}&solo_con_score=true&profile_match=true`);
    if (!res.items.length) {
      try {
        await api("/api/rescore", { method: "POST" });
        res = await api<{ items: Opp[] }>(`/api/opportunities?limit=50&score_min=${umbralActual}&solo_con_score=true&profile_match=true`);
      } catch {
        // Perfil incompleto: se conserva el estado vacío guiado.
      }
    }
    if (!res.items.length) {
      // Evita dejar el dashboard vacío cuando solo hay coincidencias medias.
      res = await api<{ items: Opp[] }>(`/api/opportunities?limit=50&score_min=${Math.max(1, umbralActual)}&solo_con_score=true&profile_match=false`);
    }
    setTop(res.items
      .filter((o) => o.score !== null)
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .slice(0, 5));
    } finally {
      setCargandoTop(false);
    }
  }

  useEffect(() => {
    Promise.all([
      api<AlertPrefs>("/api/alerts/prefs"),
      api<Metrics>("/api/dashboard/metrics?compatibility_threshold=50&new_days=7"),
    ]).then(([alertPrefs, metrics]) => {
      setPrefs(alertPrefs);
      setUmbral(alertPrefs.high_score_threshold);
      setM(metrics);
      return cargar(alertPrefs.high_score_threshold, 7);
    }).catch(() => cargar().catch(() => {}));
  }, []);

  async function aplicarCriterios() {
    setGuardandoCriterios(true);
    try {
      const actual = prefs || { email_enabled: false, close_days: [10, 5, 1], digest_hour: 7, high_score_threshold: umbral };
      const actualizado = await api<AlertPrefs>("/api/alerts/prefs", { method: "PUT", body: JSON.stringify({ ...actual, high_score_threshold: umbral }) });
      setPrefs(actualizado);
      await cargar(umbral, diasNuevos);
    } finally {
      setGuardandoCriterios(false);
    }
  }

  function buscar() {
    if (!consulta.trim()) return;
    router.push(`/app/oportunidades?q=${encodeURIComponent(consulta)}`);
  }

  if (!m) return <Spinner />;

  const kpis = [
    { t: "Compatibles con tu perfil", v: m.alta_compatibilidad, tone: "green" as const, help: `Compatibilidad de ${m.umbral_compatibilidad}% o más.` },
    { t: "Procesos nuevos", v: m.procesos_nuevos_base, tone: "teal" as const, help: "Publicados en los últimos 7 días." },
    { t: "Próximos a cerrar", v: m.proximos_a_cerrar, tone: "amber" as const, help: "Procesos guardados con cierre cercano." },
    { t: "Ofertas activas", v: m.ofertas_activas, tone: "purple" as const, help: "Proyectos activos en el preparador." },
  ];

  return (
    <div className="space-y-6">
      {/* Búsqueda en lenguaje natural */}
      <Card className="p-4">
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            value={consulta}
            onChange={(e) => setConsulta(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && buscar()}
            placeholder='Consulta en lenguaje natural: "procesos abiertos de software en Bogotá superiores a 200 millones"'
          />
          <Button onClick={buscar} className="w-full whitespace-nowrap sm:w-auto sm:min-w-24">Buscar</Button>
        </div>
      </Card>

      <Card className="p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block min-w-0"><span className="text-muted mb-1 block text-xs font-medium">Compatibilidad mínima (%)</span><Input type="number" min={0} max={100} value={umbral} onChange={(e) => setUmbral(Math.min(100, Math.max(0, Number(e.target.value))))} /></label>
          <label className="block min-w-0"><span className="text-muted mb-1 block text-xs font-medium">Procesos nuevos en los últimos días</span><Input type="number" min={1} max={90} value={diasNuevos} onChange={(e) => setDiasNuevos(Math.min(90, Math.max(1, Number(e.target.value))))} /></label>
          <Button onClick={aplicarCriterios} disabled={guardandoCriterios} className="w-full sm:col-span-2 sm:w-auto">{guardandoCriterios ? "Aplicando…" : "Aplicar criterios"}</Button>
        </div>
        <p className="text-muted mt-2 text-[11px]">Estos criterios actualizan los indicadores y el ranking. El porcentaje también se usa para tus alertas de compatibilidad.</p>
      </Card>

      {/* KPIs */}
      <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.map((k) => (
          <Card key={k.t} className="p-4">
            <p className="text-muted text-xs">{k.t}</p>
            <p className="mt-1 text-2xl font-bold tracking-tight tabular-nums">{k.v.toLocaleString("es-CO")}</p>
            <p className="text-muted my-2 text-[11px]">{k.help}</p><Badge tone={k.tone}>{k.v ? "Revisar" : "Al día"}</Badge>
          </Card>
        ))}
      </div>

      <div className="grid min-w-0 gap-6 xl:grid-cols-2">
        {/* Top oportunidades */}
        <Card>
          <CardHeader
            title="Mejores oportunidades"
            subtitle="Ranking por compatibilidad"
            action={<Link href="/app/oportunidades"><Button variant="outline" size="sm">Ver todas</Button></Link>}
          />
          {cargandoTop ? (
            <div className="flex min-h-56 flex-col items-center justify-center p-6 text-center">
              <div className="relative h-16 w-16 overflow-hidden rounded-xl border border-teal/30 bg-slate-100 p-2 dark:bg-slate-950/70" aria-hidden="true">
                <span className="absolute bottom-2 left-3 h-3 w-3 rounded-sm bg-teal animate-[tetris-fall-1_2.4s_linear_infinite]" />
                <span className="absolute bottom-2 left-6 h-3 w-3 rounded-sm bg-cyan-300 animate-[tetris-fall-2_2.8s_linear_infinite_.35s]" />
                <span className="absolute bottom-2 left-9 h-3 w-3 rounded-sm bg-amber-300 animate-[tetris-fall-3_3s_linear_infinite_.8s]" />
              </div>
              <p className="mt-4 text-sm font-semibold">Buscando tus mejores oportunidades</p>
              <p className="text-muted mt-1 text-xs">Estamos cruzando tu perfil con los procesos vigentes.</p>
            </div>
          ) : top.length === 0 ? (
            <EmptyState title="Aún no encontramos coincidencias" body="Completa tu perfil y revisa Oportunidades para calcular las mejores coincidencias disponibles." />
          ) : (
            <div className="divide-y divide-[var(--border)]">
              {top.map((o) => (
                <Link key={o.id} href={`/app/oportunidades/${o.id}`} className="block px-5 py-3 transition hover:bg-brand-50/50 dark:hover:bg-slate-800/40">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{o.objeto || "Proceso"}</p>
                      <p className="text-muted truncate text-xs">{o.entidad} · {o.departamento || "N/D"}</p>
                    </div>
                    <span className="shrink-0 whitespace-nowrap"><Badge tone={scoreTone(o.score)}><span className="whitespace-nowrap">{o.score !== null ? `${Math.round(o.score)}%` : "—"}</span></Badge></span>
                  </div>
                  <p className="text-muted mt-1 text-[11px]">{fmtCOP(o.valor)} · {o.estado}</p>
                </Link>
              ))}
            </div>
          )}
        </Card>
        <Card className="p-5">
          <h2 className="text-sm font-semibold">Qué puedes hacer ahora</h2>
          <div className="rounded-xl border border-teal/20 bg-teal/5 px-4 py-5 text-center dark:bg-teal/10">
            <p className="font-serif text-base italic leading-relaxed text-slate-700 dark:text-slate-200">“{fraseCalma}”</p>
            <p className="text-muted mt-2 text-[10px] uppercase tracking-[0.18em]">Un momento de calma para enfocar tu siguiente paso</p>
          </div>
          <div className="mt-4 space-y-3 text-sm">
            <Link href="/app/perfil" className="block rounded-lg border border-base p-3 transition hover:border-teal"><span className="font-semibold">1. Completa tu perfil</span><span className="text-muted mt-1 block text-xs">Define actividades, ubicaciones, presupuesto y modalidades.</span></Link>
            <Link href="/app/oportunidades" className="block rounded-lg border border-base p-3 transition hover:border-teal"><span className="font-semibold">2. Revisa oportunidades</span><span className="text-muted mt-1 block text-xs">Filtra procesos y abre el expediente oficial en SECOP.</span></Link>
            <Link href="/app/alertas" className="block rounded-lg border border-base p-3 transition hover:border-teal"><span className="font-semibold">3. Activa alertas</span><span className="text-muted mt-1 block text-xs">Recibe avisos cuando aparezcan procesos compatibles.</span></Link>
          </div>
        </Card>
      </div>
      {guardandoCriterios ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4" role="dialog" aria-modal="true" aria-label="Actualizando criterios">
          <div className="w-full max-w-sm rounded-2xl border border-teal/40 bg-surface p-7 text-center text-[var(--text)] shadow-2xl">
            <div className="mx-auto h-20 w-20 rounded-xl border border-teal/30 bg-slate-100 p-2 dark:bg-slate-950/70" aria-hidden="true">
              <div className="relative h-full overflow-hidden rounded-lg">
                <span className="absolute bottom-1 left-3 h-3 w-3 rounded-sm bg-teal animate-[tetris-fall-1_2.4s_linear_infinite]" />
                <span className="absolute bottom-1 left-6 h-3 w-3 rounded-sm bg-cyan-300 animate-[tetris-fall-2_2.8s_linear_infinite_.35s]" />
                <span className="absolute bottom-1 left-9 h-3 w-3 rounded-sm bg-amber-300 animate-[tetris-fall-3_3s_linear_infinite_.8s]" />
              </div>
            </div>
            <h2 className="mt-5 text-xl font-extrabold tracking-tight text-slate-900 dark:text-white">Estamos actualizando tu panel</h2>
            <p className="mt-3 text-sm font-medium leading-relaxed text-slate-600 dark:text-slate-300">Estamos recalculando las coincidencias y los indicadores con tus nuevos criterios.</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
