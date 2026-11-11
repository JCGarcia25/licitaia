"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

type Guide = {
  id: string;
  title: string;
  summary: string;
  category: string;
  minutes: number;
  href: string;
  pro?: boolean;
  steps: string[];
};

const GUIDES: Guide[] = [
  { id: "inicio", title: "Primeros pasos en MySECOP", summary: "Conoce el recorrido recomendado para encontrar oportunidades con confianza.", category: "Comenzar", minutes: 3, href: "/app", steps: ["Completa el perfil de tu empresa con actividades, servicios, ubicación y presupuesto.", "Realiza una sincronización para consultar información actualizada de SECOP.", "Revisa las oportunidades sugeridas y abre siempre la fuente oficial antes de decidir."] },
  { id: "perfil", title: "Cómo diligenciar el perfil de tu empresa", summary: "Aprende qué información escribir para obtener coincidencias más útiles.", category: "Comenzar", minutes: 5, href: "/app/perfil", steps: ["Describe con palabras concretas qué hace tu empresa y qué vende.", "Selecciona una o varias ubicaciones y modalidades que realmente atiendas.", "Guarda los cambios y vuelve a Oportunidades para actualizar las coincidencias."] },
  { id: "oportunidades", title: "Buscar y entender oportunidades", summary: "Usa el lenguaje natural y los filtros sin perderte entre opciones.", category: "Oportunidades", minutes: 4, href: "/app/oportunidades", steps: ["Escribe una palabra o una frase, por ejemplo: ‘servicios de aseo en Bogotá’. ", "Ajusta ubicación, modalidad, valor y probabilidad según lo que necesitas.", "Lee la coincidencia estimada como una orientación y verifica el proceso en SECOP."] },
  { id: "alertas", title: "Recibir alertas a tiempo", summary: "Configura umbrales, recordatorios y destinatarios para no dejar pasar una oportunidad.", category: "Seguimiento", minutes: 4, href: "/app/alertas", pro: true, steps: ["Define el porcentaje mínimo de compatibilidad que quieres vigilar.", "Indica cuántos días antes del cierre deseas recibir un recordatorio.", "Activa el resumen por correo solo cuando hayas confirmado los destinatarios."] },
  { id: "ofertas", title: "Organizar una oferta", summary: "Convierte una oportunidad en un proyecto ordenado y revisable.", category: "Preparar", minutes: 5, href: "/app/ofertas", pro: true, steps: ["Crea el proyecto desde una oportunidad que quieras estudiar.", "Completa el checklist, el cronograma y los borradores con información verificada.", "Antes de presentar, revisa todo y recuerda que la entrega en SECOP es manual."] },
  { id: "secop", title: "Sincronizar con SECOP", summary: "Actualiza los procesos disponibles desde las fuentes oficiales.", category: "Datos", minutes: 3, href: "/app/sincronizacion", pro: true, steps: ["Elige ‘Todas las fuentes oficiales SECOP’.", "Ejecuta la sincronización y espera el mensaje de finalización.", "Consulta el historial para conocer registros nuevos, existentes y errores."] },
  { id: "planes", title: "MySECOP Free y MySECOP Pro", summary: "Entiende qué incluye cada plan y cuándo conviene actualizar.", category: "Cuenta", minutes: 2, href: "/app/plan", steps: ["Free te permite descubrir oportunidades y crear el hábito de búsqueda.", "Pro desbloquea análisis, alertas, sincronización avanzada y preparador de ofertas.", "Puedes revisar el estado de tu plan desde la etiqueta superior de la aplicación."] },
];

export default function ManualesPage() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Guide | null>(null);
  const filtered = useMemo(() => {
    const value = query.trim().toLocaleLowerCase();
    if (!value) return GUIDES;
    return GUIDES.filter((guide) => `${guide.title} ${guide.summary} ${guide.category}`.toLocaleLowerCase().includes(value));
  }, [query]);

  return (
    <div className="space-y-6">
      <section className="surface-card overflow-hidden bg-gradient-to-br from-[var(--surface)] to-teal/5 p-6 sm:p-8">
        <div className="max-w-3xl">
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">Centro de ayuda</span>
          <h1 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">Aprende a sacarle más provecho a MySECOP</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted sm:text-base">Guías breves, claras y prácticas para encontrar oportunidades, organizar tu trabajo y tomar mejores decisiones de contratación pública.</p>
          <label className="mt-6 flex items-center gap-3 rounded-xl border border-base bg-[var(--bg)] px-4 py-3 focus-within:border-teal">
            <span aria-hidden="true" className="text-muted">⌕</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="¿Qué quieres aprender? Ej. alertas" className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted" aria-label="Buscar en el centro de ayuda" />
          </label>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section>
          <div className="mb-3 flex items-end justify-between gap-3"><div><h2 className="text-lg font-semibold">Guías recomendadas</h2><p className="text-sm text-muted">Elige una guía y avanza a tu ritmo.</p></div><span className="text-xs text-muted">{filtered.length} guías</span></div>
          {filtered.length ? <div className="grid gap-3 sm:grid-cols-2">{filtered.map((guide) => <article key={guide.id} className="surface-card flex flex-col p-5 transition hover:-translate-y-0.5 hover:border-teal/60"><div className="flex items-start justify-between gap-3"><span className="rounded-full bg-teal/10 px-2.5 py-1 text-[11px] font-semibold text-teal">{guide.category}</span>{guide.pro && <span className="rounded-full bg-amber-500/10 px-2.5 py-1 text-[10px] font-bold text-amber-700 dark:text-amber-200">PRO</span>}</div><h3 className="mt-4 font-semibold">{guide.title}</h3><p className="mt-2 flex-1 text-sm leading-5 text-muted">{guide.summary}</p><div className="mt-5 flex items-center justify-between gap-3"><span className="text-xs text-muted">{guide.minutes} min de lectura</span><button onClick={() => setSelected(guide)} className="rounded-lg border border-base px-3 py-2 text-xs font-semibold transition hover:border-teal hover:text-teal">Ver guía</button></div></article>)}</div> : <div className="surface-card p-8 text-center"><p className="font-semibold">No encontramos una guía con ese término</p><p className="mt-2 text-sm text-muted">Prueba con “perfil”, “oportunidades” o “alertas”.</p></div>}
        </section>
        <aside className="surface-card h-fit p-5"><h2 className="font-semibold">¿Necesitas orientación?</h2><p className="mt-2 text-sm leading-5 text-muted">Empieza por tu perfil: cuanto más claro esté, más precisas serán tus coincidencias.</p><Link href="/app/perfil" className="mt-4 inline-flex w-full items-center justify-center rounded-lg bg-teal px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:brightness-105">Revisar mi perfil</Link><Link href="/app/ayuda" className="mt-2 inline-flex w-full items-center justify-center rounded-lg border border-base px-4 py-2.5 text-sm font-semibold transition hover:border-teal hover:text-teal">Enviar una sugerencia</Link></aside>
      </div>

      {selected && <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/60 p-3 sm:items-center sm:p-6" role="dialog" aria-modal="true" aria-labelledby="guide-title"><div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-base bg-[var(--surface)] p-6 shadow-2xl sm:p-8"><div className="flex items-start justify-between gap-4"><div><span className="text-xs font-semibold uppercase tracking-wider text-teal">{selected.category} · {selected.minutes} min</span><h2 id="guide-title" className="mt-2 text-xl font-bold sm:text-2xl">{selected.title}</h2></div><button onClick={() => setSelected(null)} className="rounded-lg border border-base px-3 py-2 text-sm" aria-label="Cerrar guía">Cerrar</button></div><p className="mt-4 text-sm leading-6 text-muted">{selected.summary}</p><ol className="mt-6 space-y-3">{selected.steps.map((step, index) => <li key={step} className="flex gap-3 rounded-xl border border-base bg-[var(--bg)] p-4 text-sm leading-5"><span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-teal font-bold text-xs text-slate-950">{index + 1}</span><span>{step}</span></li>)}</ol><div className="mt-6 flex flex-wrap gap-3"><Link href={selected.href} onClick={() => setSelected(null)} className="rounded-lg bg-teal px-4 py-2.5 text-sm font-semibold text-slate-950">Ir a esta sección</Link><button onClick={() => setSelected(null)} className="rounded-lg border border-base px-4 py-2.5 text-sm font-semibold">Seguir explorando</button></div></div></div>}
    </div>
  );
}
