"use client";
/* Landing comercial de LicitaIA. */
import Link from "next/link";
import { Button } from "@/components/ui";
import { ThemeToggle } from "@/components/theme";

const PASOS = [
  { n: "1", t: "Describe tu empresa", d: "Sector, productos, códigos UNSPSC, ubicaciones de interés, presupuesto y modalidades preferidas." },
  { n: "2", t: "El agente caza oportunidades", d: "Monitorea SECOP II de forma continua y puntúa cada proceso de 0 a 100 según su compatibilidad real con tu perfil." },
  { n: "3", t: "Analiza y decide", d: "Interpretación de pliegos, evaluación de viabilidad y preparación de tu oferta con checklists y borradores." },
];

const BENEFICIOS = [
  { t: "Hasta 12 horas por semana", d: "La revisión manual de SECOP consume jornadas enteras. El agente filtra y prioriza por ti." },
  { t: "Cero oportunidades perdidas", d: "Sincronización cada 30 minutos con alertas de alta compatibilidad y recordatorios de cierre." },
  { t: "Decisiones con evidencia", d: "Cada coincidencia cita el campo del registro oficial que la sustenta. Nada es una caja negra." },
  { t: "Pliegos interpretados", d: "Requisitos, garantías y riesgos extraídos con cita de página y nivel de confianza." },
];

const COMPARACION = [
  ["Búsqueda manual en SECOP", "Búsqueda asistida con LicitaIA"],
  ["Revisión periódica manual de portales", "Monitoreo automático cada 30 minutos"],
  ["Lectura completa de cientos de procesos", "Ranking de compatibilidad 0-100 con razones"],
  ["Interpretación humana de pliegos extensos", "Matriz de requisitos con citas y nivel de confianza"],
  ["Criterios dispersos en hojas de cálculo", "Evaluador de viabilidad con pesos configurables"],
  ["Checklists improvisados por correo", "Checklist documental, versiones y exportación"],
];

const FUNCIONES = [
  { t: "Cazador de Oportunidades", d: "Búsqueda semántica y léxica sobre procesos SECOP II con puntaje de compatibilidad y razones verificables." },
  { t: "Analista de Pliegos", d: "Extrae objeto, presupuesto, cierre, requisitos, garantías y riesgos de PDF, DOCX y XLSX con cita documental." },
  { t: "Evaluador de Viabilidad", d: "Puntaje global ponderado (configurable) con requisitos críticos, fortalezas, debilidades y costo estimado de preparar la oferta." },
  { t: "Preparador de Ofertas", d: "Checklist documental, borradores de cartas, matriz de cumplimiento, cronograma y exportación a Word, PDF y Excel." },
  { t: "Alertas inteligentes", d: "Alta compatibilidad, procesos nuevos y recordatorios de cierre D-10, D-5 y D-1. Resumen diario opcional por correo." },
  { t: "Búsqueda en lenguaje natural", d: "\"Procesos abiertos de software en Bogotá superiores a $200 millones que cierren en 20 días\"." },
];

const PLANES = [
  {
    nombre: "Explorador", precio: "Gratis", detalle: "Para conocer la plataforma",
    rasgos: ["Perfil empresarial completo", "20 oportunidades puntuadas al mes", "3 análisis de pliegos al mes", "Alertas in-app básicas"],
    cta: "Comenzar gratis", destacado: false,
  },
  {
    nombre: "Profesional", precio: "$ 290.000 COP", detalle: "por mes · todo el equipo comercial",
    rasgos: ["Oportunidades y alertas ilimitadas", "Análisis de pliegos ilimitado", "Evaluador de viabilidad configurable", "Preparador de ofertas y exportación", "Recordatorios de cierre y resumen diario"],
    cta: "Probar 14 días", destacado: true,
  },
  {
    nombre: "Corporativo", precio: "A la medida", detalle: "consorcios y gerencias de contratación",
    rasgos: ["Múltiples perfiles de empresa", "Historial de contratos y competencia", "Soporte prioritario y capacitación", "Integraciones y SSO"],
    cta: "Hablar con ventas", destacado: false,
  },
];

const FAQ = [
  { q: "¿LicitaIA es una plataforma del Gobierno colombiano?", a: "No. LicitaIA es un producto independiente que consulta fuentes públicas oficiales (SECOP en datos.gov.co y Colombia Compra Eficiente) y siempre muestra el enlace al expediente original. La fuente oficial es la referencia definitiva." },
  { q: "¿Cómo calcula el puntaje de compatibilidad?", a: "El Cazador combina palabras clave, códigos UNSPSC, ubicación, cuantía y modalidad con búsqueda semántica sobre el objeto contractual. Cada punto incluye la razón verificable que lo sustenta." },
  { q: "¿El puntaje de viabilidad garantiza que ganaré la licitación?", a: "No. Es una evaluación de conveniencia de participación con pesos configurables de LicitaIA. No constituye una probabilidad de adjudicación ni un criterio oficial de ninguna entidad." },
  { q: "¿El sistema presenta propuestas en SECOP?", a: "No. LicitaIA prepara checklists, borradores y matrices, pero la presentación en SECOP la realiza siempre una persona autorizada de tu empresa." },
  { q: "¿Qué documentos puede analizar?", a: "PDF, DOCX y XLSX que cargues, o documentos oficiales accesibles mediante enlaces públicos permitidos. Cada hallazgo cita documento, página o sección y su nivel de confianza." },
  { q: "¿Qué pasa con mis datos?", a: "Tus perfiles, documentos y ofertas son privados, se almacenan cifrados en reposo en producción y no se comparten con terceros. Puedes exportarlos o eliminarlos cuando quieras." },
];

export default function Landing() {
  return (
    <div className="min-h-screen">
      {/* ---------- Header ---------- */}
      <header className="sticky top-0 z-40 border-b border-base bg-[var(--bg)]/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-900 font-bold text-white dark:bg-teal dark:text-slate-950">L</span>
            <span className="text-lg font-bold tracking-tight">LicitaIA</span>
          </Link>
          <nav className="text-muted hidden items-center gap-6 text-sm md:flex">
            <a href="#como-funciona" className="hover:text-teal transition">Cómo funciona</a>
            <a href="#funciones" className="hover:text-teal transition">Funciones</a>
            <a href="#planes" className="hover:text-teal transition">Planes</a>
            <a href="#faq" className="hover:text-teal transition">FAQ</a>
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link href="/iniciar-sesion"><Button variant="outline" size="sm">Iniciar sesión</Button></Link>
            <Link href="/registro"><Button size="sm">Comenzar gratis</Button></Link>
          </div>
        </div>
      </header>

      {/* ---------- Hero ---------- */}
      <section className="hero-grid border-b border-base">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-5 py-20 md:grid-cols-2 md:py-28">
          <div className="animate-fadeUp">
            <span className="text-teal mb-4 inline-flex items-center gap-2 rounded-full border border-base px-3 py-1 text-xs font-medium">
              <span className="h-1.5 w-1.5 animate-pulseSoft rounded-full bg-teal" /> Monitoreo continuo de SECOP II
            </span>
            <h1 className="text-4xl font-extrabold leading-tight tracking-tight md:text-5xl">
              Encuentra las licitaciones correctas antes que tu competencia.
            </h1>
            <p className="text-muted mt-5 text-lg">
              Tu agente de inteligencia artificial monitorea la contratación pública, analiza requisitos y descubre oportunidades para tu empresa.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/registro"><Button className="px-6 py-3">Comenzar gratis</Button></Link>
              <a href="#como-funciona"><Button variant="outline" className="px-6 py-3">Ver cómo funciona</Button></a>
            </div>
            <p className="text-muted mt-6 text-xs">
              LicitaIA no es una plataforma oficial del Gobierno colombiano. Consulta fuentes públicas y siempre muestra el expediente original.
            </p>
          </div>

          {/* Demostración visual del agente (sección 2) */}
          <div className="surface-card shadow-lift animate-fadeUp p-5">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-semibold">Agente · Cazador de Oportunidades</span>
              <span className="flex items-center gap-1 text-[11px] text-teal"><span className="h-1.5 w-1.5 animate-pulseSoft rounded-full bg-teal" /> buscando en SECOP II</span>
            </div>
            <div className="mb-4 rounded-lg border border-base bg-[var(--bg)] px-3 py-2 text-xs">
              <span className="text-muted">consulta:</span> procesos de desarrollo de software en Bogotá &gt; $ 200 millones
            </div>
            <div className="space-y-2">
              {[
                { e: "Secretaría Distrital de Gobierno", s: 92, m: "software · UNSPSC 81101500 · Bogotá D.C." },
                { e: "Universidad Nacional del Quindío", s: 61, m: "aplicaciones · licitación pública" },
                { e: "E.S.E. Hospital Regional del Meta", s: 18, m: "equipos biomédicos · sin coincidencia" },
              ].map((o, i) => (
                <div key={i} className="flex items-center gap-3 rounded-lg border border-base px-3 py-2.5" style={{ animation: `fadeUp .6s ease ${i * 0.15}s both` }}>
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-bold text-brand-800 dark:bg-slate-800 dark:text-brand-300">
                    {o.s}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium">{o.e}</p>
                    <p className="text-muted truncate text-[11px]">{o.m}</p>
                  </div>
                  <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                    <div className="h-full rounded-full bg-teal" style={{ width: `${o.s}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <p className="text-muted mt-3 text-[11px]">Datos ilustrativos. Cada resultado incluye el enlace al expediente original en SECOP.</p>
          </div>
        </div>
      </section>

      {/* ---------- 1. Cómo funciona ---------- */}
      <section id="como-funciona" className="border-b border-base py-20">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">Cómo funciona LicitaIA en tres pasos</h2>
          <p className="text-muted mx-auto mt-3 max-w-2xl text-center">
            La inteligencia detrás de tu próxima licitación opera en el fondo mientras tu equipo decide dónde competir.
          </p>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {PASOS.map((p) => (
              <div key={p.n} className="surface-card shadow-card p-6 transition hover:shadow-lift">
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-900 font-bold text-white dark:bg-teal dark:text-slate-950">{p.n}</div>
                <h3 className="font-semibold">{p.t}</h3>
                <p className="text-muted mt-2 text-sm">{p.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 3. Beneficios ---------- */}
      <section className="border-b border-base bg-brand-900 py-20 text-white dark:bg-slate-950">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-3xl font-bold tracking-tight">Beneficios y ahorro de tiempo</h2>
          <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {BENEFICIOS.map((b) => (
              <div key={b.t} className="rounded-xl border border-white/10 bg-white/5 p-6">
                <h3 className="font-semibold text-teal">{b.t}</h3>
                <p className="mt-2 text-sm text-white/80">{b.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 4. Comparación ---------- */}
      <section className="border-b border-base py-20">
        <div className="mx-auto max-w-4xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">Búsqueda manual vs. búsqueda asistida con IA</h2>
          <div className="surface-card shadow-card mt-10 overflow-hidden">
            {COMPARACION.map((fila, i) => (
              <div key={i} className={`grid grid-cols-2 gap-4 px-6 py-4 text-sm ${i === 0 ? "border-b border-base bg-brand-50 font-semibold dark:bg-slate-800/60" : "border-b border-base last:border-0"}`}>
                <span className={i === 0 ? "" : "text-muted"}>{fila[0]}</span>
                <span className={i === 0 ? "" : "font-medium text-teal"}>{fila[1]}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 5. Funciones inteligentes ---------- */}
      <section id="funciones" className="border-b border-base py-20">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">Funciones inteligentes</h2>
          <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {FUNCIONES.map((f) => (
              <div key={f.t} className="surface-card shadow-card p-6 transition hover:-translate-y-0.5 hover:shadow-lift">
                <h3 className="font-semibold">{f.t}</h3>
                <p className="text-muted mt-2 text-sm">{f.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 6. Planes y precios ---------- */}
      <section id="planes" className="border-b border-base py-20">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">Planes y precios</h2>
          <p className="text-muted mt-3 text-center">Precios en pesos colombianos (COP). Sin contratos de permanencia.</p>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {PLANES.map((p) => (
              <div key={p.nombre} className={`surface-card relative p-7 ${p.destacado ? "shadow-lift ring-2 ring-teal" : "shadow-card"}`}>
                {p.destacado ? (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-teal px-3 py-1 text-[11px] font-semibold text-slate-950">Más elegido</span>
                ) : null}
                <h3 className="font-semibold">{p.nombre}</h3>
                <p className="mt-2 text-2xl font-extrabold">{p.precio}</p>
                <p className="text-muted text-xs">{p.detalle}</p>
                <ul className="mt-5 space-y-2 text-sm">
                  {p.rasgos.map((r) => (
                    <li key={r} className="flex gap-2"><span className="text-teal">✓</span><span className="text-muted">{r}</span></li>
                  ))}
                </ul>
                <Link href="/registro" className="mt-6 block">
                  <Button variant={p.destacado ? "primary" : "outline"} className="w-full">{p.cta}</Button>
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 7. FAQ ---------- */}
      <section id="faq" className="border-b border-base py-20">
        <div className="mx-auto max-w-3xl px-5">
          <h2 className="text-center text-3xl font-bold tracking-tight">Preguntas frecuentes</h2>
          <div className="mt-10 space-y-3">
            {FAQ.map((f) => (
              <details key={f.q} className="surface-card group px-5 py-4">
                <summary className="cursor-pointer list-none text-sm font-medium">
                  <span className="text-teal mr-2 transition group-open:rotate-90 inline-block">▸</span>{f.q}
                </summary>
                <p className="text-muted mt-3 pl-5 text-sm">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- 8. Registro gratuito ---------- */}
      <section className="py-20">
        <div className="mx-auto max-w-3xl px-5 text-center">
          <h2 className="text-3xl font-bold tracking-tight">Empieza a recibir oportunidades hoy</h2>
          <p className="text-muted mx-auto mt-3 max-w-xl">
            Crea tu cuenta gratis, describe tu empresa y deja que el agente trabaje. Sin tarjeta de crédito.
          </p>
          <Link href="/registro" className="mt-8 inline-block">
            <Button className="px-8 py-3 text-base">Crear cuenta gratis</Button>
          </Link>
        </div>
      </section>

      {/* ---------- 9. Footer legal ---------- */}
      <footer className="border-t border-base py-12">
        <div className="text-muted mx-auto max-w-6xl space-y-4 px-5 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <span className="flex items-center gap-2 text-sm font-bold text-[var(--text)]">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-brand-900 text-white dark:bg-teal dark:text-slate-950">L</span>
              LicitaIA
            </span>
            <nav className="flex flex-wrap gap-5">
              <a href="#" className="hover:text-teal">Términos y condiciones</a>
              <a href="#" className="hover:text-teal">Política de privacidad</a>
              <a href="#" className="hover:text-teal">Tratamiento de datos (Ley 1581)</a>
              <a href="#" className="hover:text-teal">Contacto</a>
            </nav>
          </div>
          <p className="max-w-3xl leading-relaxed">
            Aviso legal: LicitaIA es un producto independiente de análisis de información pública y <strong>no es una plataforma
            oficial del Gobierno colombiano</strong>, ni está afiliado a Colombia Compra Eficiente. Los datos provienen de fuentes
            públicas (SECOP en datos.gov.co); la fuente oficial permanece como referencia definitiva. Los puntajes y evaluaciones
            son orientativos, no constituyen asesoría legal ni probabilidades de adjudicación, y requieren validación humana.
          </p>
          <p>© {new Date().getFullYear()} LicitaIA · La inteligencia detrás de tu próxima licitación.</p>
        </div>
      </footer>
    </div>
  );
}
