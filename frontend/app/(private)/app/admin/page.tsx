"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Badge, Card, EmptyState, Spinner } from "@/components/ui";

type Overview = { generated_at: string; metrics: Record<string, number>; usuarios_activos: { id:number; email:string; nombre:string; ruta:string; ultimo_acceso:string; dispositivo:string }[]; usuarios: { id:number; email:string; nombre:string; ruta:string; ultimo_acceso:string|null; creado:string; activo:boolean }[]; eventos: { accion:string; entidad:string; fecha:string; usuario_id:number }[] };
const fmt = (v: string|null|undefined) => v ? new Date(v).toLocaleString("es-CO", { dateStyle:"short", timeStyle:"short" }) : "Sin actividad";

export default function AdminPage() {
  const [data, setData] = useState<Overview|null>(null); const [error, setError] = useState("");
  const cargar = useCallback(() => api<Overview>("/api/admin/overview").then(setData).catch((e) => setError(e instanceof Error ? e.message : "No se pudo cargar el panel")), []);
  async function cambiarEstado(id: number, activo: boolean) {
    const mensaje = activo ? "¿Activar nuevamente este usuario?" : "¿Desactivar este usuario? No podrá iniciar sesión, pero sus datos se conservarán.";
    if (!window.confirm(mensaje)) return;
    try { await api(`/api/admin/users/${id}/status`, { method: "PATCH", body: JSON.stringify({ activo }) }); await cargar(); }
    catch (e) { setError(e instanceof Error ? e.message : "No fue posible actualizar el usuario"); }
  }
  useEffect(() => { cargar(); const t = window.setInterval(cargar, 30000); return () => window.clearInterval(t); }, [cargar]);
  if (error) return <Card><EmptyState title="Panel no disponible" body={error} /></Card>;
  if (!data) return <Spinner label="Cargando centro de control…" />;
  const cards = [["Usuarios totales", data.metrics.usuarios], ["Activos ahora", data.metrics.activos], ["Perfiles completos", data.metrics.perfiles_completos], ["Proyectos de oferta", data.metrics.proyectos], ["Oportunidades puntuadas", data.metrics.busquedas_puntuadas]];
  return <div className="space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[.18em] text-teal">Centro de control</p><h1 className="mt-1 text-2xl font-bold tracking-tight">Actividad de MySECOP</h1><p className="text-muted mt-1 text-sm">Usuarios, navegación y salud del producto en tiempo casi real.</p></div><Badge tone="green">Actualizado {fmt(data.generated_at)}</Badge></div>
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">{cards.map(([label,value]) => <Card key={String(label)} className="p-4"><p className="text-muted text-xs">{label}</p><p className="mt-2 text-2xl font-extrabold">{value}</p></Card>)}</div>
    <div className="grid gap-5 lg:grid-cols-5">
      <Card className="lg:col-span-3"><div className="border-b border-base px-5 py-4"><h2 className="font-semibold">Conectados ahora</h2><p className="text-muted mt-1 text-xs">Se consideran activos durante los últimos dos minutos.</p></div>{data.usuarios_activos.length ? <div className="divide-y divide-[var(--border)]">{data.usuarios_activos.map((u) => <div key={u.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4"><div className="min-w-0"><p className="truncate text-sm font-semibold">{u.nombre || u.email}</p><p className="text-muted truncate text-xs">{u.email} · {u.ruta}</p></div><div className="text-right"><Badge tone="teal">En línea</Badge><p className="text-muted mt-1 max-w-44 truncate text-[10px]">{u.dispositivo}</p></div></div>)}</div> : <EmptyState title="No hay usuarios conectados" body="La actividad aparecerá aquí cuando alguien navegue en MySECOP." />}</Card>
      <Card className="lg:col-span-2"><div className="border-b border-base px-5 py-4"><h2 className="font-semibold">Actividad reciente</h2><p className="text-muted mt-1 text-xs">Últimos eventos registrados.</p></div>{data.eventos.length ? <div className="divide-y divide-[var(--border)]">{data.eventos.map((e,i) => <div key={i} className="px-5 py-3"><p className="text-xs font-medium">{e.accion.replaceAll("_", " ")}</p><p className="text-muted mt-1 text-[11px]">{e.entidad} · {fmt(e.fecha)}</p></div>)}</div> : <EmptyState title="Aún no hay eventos" />}</Card>
    </div>
    <Card><div className="border-b border-base px-5 py-4"><h2 className="font-semibold">Usuarios registrados</h2><p className="text-muted mt-1 text-xs">Desactivar bloquea el acceso sin borrar la información histórica.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead><tr className="border-b border-base text-muted"><th className="px-5 py-3">Usuario</th><th className="px-5 py-3">Estado</th><th className="px-5 py-3">Último módulo</th><th className="px-5 py-3">Última actividad</th><th className="px-5 py-3">Acción</th></tr></thead><tbody>{data.usuarios.map((u) => <tr key={u.id} className="border-b border-base last:border-0"><td className="px-5 py-3"><p className="font-medium">{u.nombre || "Sin nombre"}</p><p className="text-muted">{u.email}</p></td><td className="px-5 py-3"><Badge tone={u.activo ? "green" : "gray"}>{u.activo ? "Activo" : "Desactivado"}</Badge></td><td className="px-5 py-3">{u.ruta}</td><td className="px-5 py-3">{fmt(u.ultimo_acceso)}</td><td className="px-5 py-3"><button type="button" onClick={() => cambiarEstado(u.id, !u.activo)} className={`rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold ${u.activo ? "border-red-400/40 text-red-400 hover:bg-red-400/10" : "border-teal/40 text-teal hover:bg-teal/10"}`}>{u.activo ? "Desactivar" : "Activar"}</button></td></tr>)}</tbody></table></div></Card>
  </div>;
}
