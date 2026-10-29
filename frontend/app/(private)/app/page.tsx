"use client";
/* Dashboard ejecutivo: métricas, tendencia y top oportunidades. */
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
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
    const res = await api<{ items: Opp[] }>("/api/opportunities?limit=5&score_min=1");
    setTop(res.items.filter((o) => o.score !== null));
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
    { t: "Oportunidades detectadas", v: m.oportunidades_detectadas, tone: "blue" as const },
    { t: "Procesos nuevos (7 días)", v: m.procesos_nuevos_base, tone: "teal" as const },
    { t: "Alta compatibilidad", v: m.alta_compatibilidad, tone: "green" as const },
    { t: "Próximas a cerrar", v: m.proximos_a_cerrar, tone: "amber" as const },
    { t: "Guardadas", v: m.guardadas, tone: "blue" as const },
    { t: "Proyectos de propuesta", v: m.proyectos_propuesta, tone: "purple" as const },
    { t: "Docs. por revisar", v: m.documentos_pendientes, tone: "amber" as const },
    { t: "Descartadas", v: m.descartadas, tone: "gray" as const },
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
            <div className="mt-2"><Badge tone={k.tone}>live</Badge></div>
          </Card>
        ))}
      </div>

      {/* Valor agregado */}
      <Card className="p-5">
        <p className="text-muted text-xs">Valor agregado de oportunidades de alta compatibilidad</p>
        <p className="mt-1 text-3xl font-extrabold text-teal">{fmtCOP(m.valor_agregado_cop)}</p>
        <p className="text-muted mt-1 text-[11px]">Suma de valores estimados de procesos con compatibilidad ≥ 70.</p>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Tendencia */}
        <Card>
          <CardHeader title="Tendencia de oportunidades por mes" subtitle="Según fecha de publicación en la fuente" />
          <div className="h-64 p-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={m.tendencia_mensual}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={28} />
                <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, fontSize: 12 }} />
                <Bar dataKey="total" fill="#14B8A6" radius={[6, 6, 0, 0]} name="Oportunidades" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Top oportunidades */}
        <Card>
          <CardHeader
            title="Mejores oportunidades"
            subtitle="Ranking por compatibilidad"
            action={<Link href="/app/oportunidades"><Button variant="outline" size="sm">Ver todas</Button></Link>}
          />
          {top.length === 0 ? (
            <EmptyState title="Aún no hay oportunidades puntuadas" body="Completa tu perfil y ejecuta el agente desde Oportunidades." />
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
      </div>
    </div>
  );
}
