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
  valor_agregado_cop: number;
  guardadas: number;
  descartadas: number;
  proyectos_propuesta: number;
  documentos_pendientes: number;
  alertas_no_leidas: number;
  tendencia_mensual: { mes: string; total: number }[];
};

type Opp = {
  id: number; entidad: string; objeto: string; valor: number | null; estado: string;
  departamento: string | null; score: number | null; url_oficial: string | null;
};

export default function Dashboard() {
  const [m, setM] = useState<Metrics | null>(null);
  const [top, setTop] = useState<Opp[]>([]);
  const [consulta, setConsulta] = useState("");
  const router = useRouter();

  async function cargar() {
    const metrics = await api<Metrics>("/api/dashboard/metrics");
    setM(metrics);
    // Mantener el mismo criterio que la vista Oportunidades: solo procesos
    // compatibles con el perfil y con una puntuación mínima significativa.
    let res = await api<{ items: Opp[] }>("/api/opportunities?limit=50&score_min=40&solo_con_score=true&profile_match=true");
    if (!res.items.length) {
      try {
        await api("/api/rescore", { method: "POST" });
        res = await api<{ items: Opp[] }>("/api/opportunities?limit=50&score_min=40&solo_con_score=true&profile_match=true");
      } catch {
        // Perfil incompleto: se conserva el estado vacío guiado.
      }
    }
    if (!res.items.length) {
      // Evita dejar el dashboard vacío cuando solo hay coincidencias medias.
      res = await api<{ items: Opp[] }>("/api/opportunities?limit=50&score_min=1&solo_con_score=true&profile_match=false");
    }
    setTop(res.items
      .filter((o) => o.score !== null)
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .slice(0, 5));
  }

  useEffect(() => {
    cargar().catch(() => {});
  }, []);

  function buscar() {
    if (!consulta.trim()) return;
    router.push(`/app/oportunidades?q=${encodeURIComponent(consulta)}`);
  }

  if (!m) return <Spinner />;

  const kpis = [
    { t: "Compatibles con tu perfil", v: m.alta_compatibilidad, tone: "green" as const, help: "Compatibilidad de 70% o más." },
    { t: "Procesos nuevos", v: m.procesos_nuevos_base, tone: "teal" as const, help: "Publicados en los últimos 7 días." },
    { t: "Próximos a cerrar", v: m.proximos_a_cerrar, tone: "amber" as const, help: "Procesos guardados con cierre cercano." },
    { t: "Documentos por revisar", v: m.documentos_pendientes, tone: "purple" as const, help: "Análisis pendientes de revisión." },
  ];

  return (
    <div className="space-y-6">
      {/* Búsqueda en lenguaje natural */}
      <Card className="p-4">
        <div className="flex gap-2">
          <Input
            value={consulta}
            onChange={(e) => setConsulta(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && buscar()}
            placeholder='Consulta en lenguaje natural: "procesos abiertos de software en Bogotá superiores a 200 millones"'
          />
          <Button onClick={buscar}>Buscar</Button>
        </div>
      </Card>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {kpis.map((k) => (
          <Card key={k.t} className="p-4">
            <p className="text-muted text-xs">{k.t}</p>
            <p className="mt-1 text-2xl font-bold tracking-tight">{k.v}</p>
            <p className="text-muted my-2 text-[11px]">{k.help}</p><Badge tone={k.tone}>{k.v ? "Revisar" : "Al día"}</Badge>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Top oportunidades */}
        <Card>
          <CardHeader
            title="Mejores oportunidades"
            subtitle="Ranking por compatibilidad"
            action={<Link href="/app/oportunidades"><Button variant="outline" size="sm">Ver todas</Button></Link>}
          />
          {top.length === 0 ? (
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
                    <Badge tone={scoreTone(o.score)}>{o.score !== null ? `${Math.round(o.score)}%` : "—"}</Badge>
                  </div>
                  <p className="text-muted mt-1 text-[11px]">{fmtCOP(o.valor)} · {o.estado}</p>
                </Link>
              ))}
            </div>
          )}
        </Card>
        <Card className="p-5">
          <h2 className="text-sm font-semibold">Qué puedes hacer ahora</h2>
          <div className="mt-4 space-y-3 text-sm">
            <Link href="/app/perfil" className="block rounded-lg border border-base p-3 transition hover:border-teal"><span className="font-semibold">1. Completa tu perfil</span><span className="text-muted mt-1 block text-xs">Define actividades, ubicaciones, presupuesto y modalidades.</span></Link>
            <Link href="/app/oportunidades" className="block rounded-lg border border-base p-3 transition hover:border-teal"><span className="font-semibold">2. Revisa oportunidades</span><span className="text-muted mt-1 block text-xs">Filtra procesos y abre el expediente oficial en SECOP.</span></Link>
            <Link href="/app/alertas" className="block rounded-lg border border-base p-3 transition hover:border-teal"><span className="font-semibold">3. Activa alertas</span><span className="text-muted mt-1 block text-xs">Recibe avisos cuando aparezcan procesos compatibles.</span></Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
