"use client";
/* Estructura de la aplicación privada (barra lateral + topbar). */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useRef, useState } from "react";
import { AuthProvider, RequireAuth, useAuth } from "@/components/auth";
import { ThemeToggle } from "@/components/theme";
import { api, apiBackground } from "@/lib/api";
import { WorkOverlay } from "@/components/ui";

const NAV = [
  { href: "/app", label: "Resumen", icon: "▤" },
  { href: "/app/oportunidades", label: "Oportunidades", icon: "◎" },
  { href: "/app/ofertas", label: "Ofertas", icon: "✎" },
  { href: "/app/alertas", label: "Alertas", icon: "◔" },
  { href: "/app/perfil", label: "Perfil de empresa", icon: "☑" },
  { href: "/app/sincronizacion", label: "Sincronización SECOP", icon: "⇅" },
  { href: "/app/manuales", label: "Centro de ayuda", icon: "?" },
  { href: "/app/ayuda", label: "Sugerencias y reportes", icon: "♡" },
];

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <AuthenticatedLayout>{children}</AuthenticatedLayout>
    </AuthProvider>
  );
}

function AuthenticatedLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [plan, setPlan] = useState<{ nombre: string; es_pro: boolean; status: string } | null>(null);
  const [requests, setRequests] = useState(0);
  const [showWork, setShowWork] = useState(false);
  const menu = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const closeMenu = () => menu.current?.close();
  useEffect(() => { closeMenu(); }, [pathname]);
  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 1024px)");
    const onResize = () => { if (desktop.matches) closeMenu(); };
    desktop.addEventListener("change", onResize);
    return () => desktop.removeEventListener("change", onResize);
  }, []);

  useEffect(() => {
    let timer: number | undefined;
    let pending = 0;
    const start = () => {
      pending += 1;
      setRequests(pending);
      // Wait four seconds from the start of continuous work. Concurrent
      // requests must not postpone the indicator for an already slow task.
      if (pending === 1) {
        timer = window.setTimeout(() => {
          if (pending > 0) setShowWork(true);
        }, 4000);
      }
    };
    const end = () => {
      pending = Math.max(0, pending - 1);
      setRequests(pending);
      if (pending === 0) {
        window.clearTimeout(timer);
        setShowWork(false);
      }
    };
    window.addEventListener("mysecop:request-start", start);
    window.addEventListener("mysecop:request-end", end);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("mysecop:request-start", start);
      window.removeEventListener("mysecop:request-end", end);
    };
  }, []);

  useEffect(() => {
    api<{ nombre: string; es_pro: boolean; status: string }>("/api/billing")
      .then(setPlan)
      .catch(() => setPlan({ nombre: "MySECOP Free", es_pro: false, status: "activa" }));
    const onPlanUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ nombre: string; es_pro: boolean; status: string }>).detail;
      if (detail) setPlan(detail);
    };
    window.addEventListener("mysecop:billing-updated", onPlanUpdated);
    return () => window.removeEventListener("mysecop:billing-updated", onPlanUpdated);
  }, []);

  useEffect(() => {
    if (!user) return;
    const ping = () => apiBackground("/api/admin/presence", { method: "POST", body: JSON.stringify({ path: window.location.pathname }) }).catch(() => undefined);
    ping();
    const timer = window.setInterval(ping, 45000);
    return () => window.clearInterval(timer);
  }, [user, pathname]);

  return (
      <RequireAuth>
      {showWork && requests > 0 ? <WorkOverlay /> : null}
      <a href="#contenido-principal" className="skip-link">Saltar al contenido</a>
      <dialog ref={menu} aria-labelledby="menu-title" className="app-menu surface-card m-0 h-dvh max-h-dvh w-[min(90vw,22rem)] max-w-none rounded-none p-4" onClose={() => { document.body.style.overflow = ""; trigger.current?.focus(); }} onClick={(event) => { if (event.target === event.currentTarget && event.clientX > event.currentTarget.getBoundingClientRect().right) closeMenu(); }}>
        <div className="mb-4 flex items-center justify-between gap-3"><h2 id="menu-title" className="text-lg font-bold">MySECOP</h2><button type="button" onClick={closeMenu} className="min-h-11 rounded-lg border border-base px-3">Cerrar menú</button></div>
        <nav aria-label="Menú principal móvil" className="space-y-1">{NAV.map(n => <Link key={n.href} href={n.href} onClick={closeMenu} aria-current={(n.href === "/app" ? pathname === n.href : pathname.startsWith(n.href)) ? "page" : undefined} className="flex min-h-11 items-center gap-3 rounded-lg px-3 py-3 hover:bg-teal/10 aria-[current=page]:bg-teal/10 aria-[current=page]:font-semibold"><span aria-hidden="true">{n.icon}</span>{n.label}</Link>)}</nav>
        <Link href="/app/plan" onClick={closeMenu} className="mt-4 flex min-h-11 items-center rounded-lg border border-base px-3 text-sm">{plan?.nombre || "MySECOP Free"}</Link>
        {user?.email?.toLowerCase() === "jorge@zorbagames.com" && <Link href="/app/admin" onClick={closeMenu} className="mt-2 flex min-h-11 items-center px-3 text-sm">Centro de control</Link>}
      </dialog>
      <div className="flex min-h-screen bg-[var(--bg)]">
        {/* Sidebar */}
        <aside className="hidden w-64 shrink-0 border-r border-base bg-[var(--surface)] lg:block">
          <div className="flex h-20 items-center gap-3 border-b border-base px-6">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-900 text-[9px] font-bold text-white dark:bg-teal dark:text-slate-950">MS</span>
            <span className="font-bold tracking-tight">MySECOP</span>
          </div>
          <nav aria-label="Menú principal" className="space-y-1.5 p-4">
            {NAV.map((n) => {
              const activo = n.href === "/app" ? pathname === "/app" : pathname.startsWith(n.href);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  aria-current={activo ? "page" : undefined}
                  className={`flex min-h-11 items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                    activo
                      ? "bg-teal/10 font-semibold text-teal dark:bg-slate-800 dark:text-teal"
                      : "text-muted hover:bg-brand-50 hover:text-[var(--text)] dark:hover:bg-slate-800"
                  }`}
                >
                  <span className="w-4 text-center">{n.icon}</span>
                  {n.label}
                  {["/app/ofertas", "/app/alertas", "/app/sincronizacion"].includes(n.href) && !plan?.es_pro && <span className="ml-auto rounded-full bg-amber-100 px-1.5 py-0.5 text-[9px] font-bold text-amber-800 dark:bg-amber-950/50 dark:text-amber-200">PRO</span>}
                </Link>
              );
            })}
          </nav>
          <div className="mx-3 mt-4 rounded-lg border border-base bg-[var(--bg)] p-3 text-[11px] leading-relaxed text-muted">
            Información pública de SECOP y TVEC. Confirma los requisitos y los plazos en la fuente oficial.
          </div>
        </aside>

        {/* Contenido */}
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-30 flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-base bg-[var(--bg)]/90 px-4 py-3 backdrop-blur sm:px-6">
            <button ref={trigger} type="button" aria-haspopup="dialog" onClick={() => { menu.current?.showModal(); document.body.style.overflow = "hidden"; }} className="flex min-h-11 items-center gap-2 rounded-lg border border-base px-3 text-sm font-semibold lg:hidden"><span aria-hidden="true">☰</span> Menú</button>
            <div className="hidden lg:block" />
            <div className="order-1 ml-auto flex items-center gap-2 sm:gap-3 lg:order-2">
              <Link href="/app" className="mr-1 flex items-center gap-2 font-semibold lg:hidden"><span className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal text-[9px] font-bold text-slate-950">MS</span><span className="hidden sm:inline">MySECOP</span></Link>
              <ThemeToggle />
              <Link href="/app/plan" className={`hidden rounded-full border px-3 py-1 text-[11px] font-semibold sm:inline ${plan?.es_pro ? "border-teal/40 bg-teal/10 text-teal" : "border-amber-300/60 bg-amber-50 text-amber-800 dark:bg-amber-950/30 dark:text-amber-200"}`}>
                {plan?.nombre || "MySECOP Free"}
              </Link>
              {user?.email?.toLowerCase() === "jorge@zorbagames.com" ? <Link href="/app/admin" className="hidden rounded-lg border border-teal/40 px-3 py-1.5 text-xs font-semibold text-teal sm:inline">Centro de control</Link> : null}
              <span className="text-muted hidden text-xs lg:inline">{user?.email}</span>
              <button onClick={logout} className="border-base rounded-lg border min-h-11 px-3 py-1.5 text-xs font-medium transition hover:text-red-600">
                Salir
              </button>
            </div>
          </header>
          <main id="contenido-principal" tabIndex={-1} className="app-main mx-auto w-full max-w-7xl min-w-0 p-4 sm:p-6 lg:p-8">
            {plan && !plan.es_pro && <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-300/50 bg-amber-50/80 px-4 py-3 text-xs text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/25 dark:text-amber-100">
              <span><strong>MySECOP Free:</strong> análisis de pliegos, alertas por correo, sincronización avanzada y preparador de ofertas están identificados como funciones Pro.</span>
              <Link href="/app/plan" className="font-bold underline underline-offset-2">Ver MySECOP Pro</Link>
            </div>}
            {children}
          </main>
        </div>
      </div>
      </RequireAuth>
  );
}
