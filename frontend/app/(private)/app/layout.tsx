"use client";
/* Estructura de la aplicación privada (barra lateral + topbar). */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { AuthProvider, RequireAuth, useAuth } from "@/components/auth";
import { ThemeToggle } from "@/components/theme";
import { api } from "@/lib/api";

const NAV = [
  { href: "/app", label: "Dashboard", icon: "▤" },
  { href: "/app/oportunidades", label: "Oportunidades", icon: "◎" },
  { href: "/app/ofertas", label: "Ofertas", icon: "✎" },
  { href: "/app/alertas", label: "Alertas", icon: "◔" },
  { href: "/app/perfil", label: "Perfil de empresa", icon: "☑" },
  { href: "/app/sincronizacion", label: "Sincronización SECOP", icon: "⇅" },
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

  useEffect(() => {
    api<{ nombre: string; es_pro: boolean; status: string }>("/api/billing")
      .then(setPlan)
      .catch(() => setPlan({ nombre: "MySECOP Free", es_pro: false, status: "activa" }));
  }, []);

  return (
      <RequireAuth>
      <div className="flex min-h-screen bg-[var(--bg)]">
        {/* Sidebar */}
        <aside className="hidden w-64 shrink-0 border-r border-base bg-[var(--surface)] md:block">
          <div className="flex h-20 items-center gap-3 border-b border-base px-6">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-900 text-[9px] font-bold text-white dark:bg-teal dark:text-slate-950">MS</span>
            <span className="font-bold tracking-tight">MySECOP</span>
          </div>
          <nav className="space-y-1.5 p-4">
            {NAV.map((n) => {
              const activo = n.href === "/app" ? pathname === "/app" : pathname.startsWith(n.href);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                    activo
                      ? "bg-teal/10 font-semibold text-teal dark:bg-slate-800 dark:text-teal"
                      : "text-muted hover:bg-brand-50 hover:text-[var(--text)] dark:hover:bg-slate-800"
                  }`}
                >
                  <span className="w-4 text-center">{n.icon}</span>
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="mx-3 mt-4 rounded-lg border border-base bg-[var(--bg)] p-3 text-[11px] leading-relaxed text-muted">
            Fuente de datos: SECOP II (datos.gov.co). La fuente oficial es siempre la referencia definitiva.
          </div>
        </aside>

        {/* Contenido */}
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-base bg-[var(--bg)]/90 px-6 backdrop-blur">
            <div className="flex items-center gap-4 overflow-x-auto md:hidden">
              {NAV.map((n) => (
                <Link key={n.href} href={n.href} className="text-muted whitespace-nowrap text-xs hover:text-teal">{n.label}</Link>
              ))}
            </div>
            <div className="hidden md:block" />
            <div className="flex items-center gap-3">
              <ThemeToggle />
              <Link href="/app/plan" className={`hidden rounded-full border px-3 py-1 text-[11px] font-semibold sm:inline ${plan?.es_pro ? "border-teal/40 bg-teal/10 text-teal" : "border-amber-300/60 bg-amber-50 text-amber-800 dark:bg-amber-950/30 dark:text-amber-200"}`}>
                {plan?.nombre || "MySECOP Free"}
              </Link>
              <span className="text-muted hidden text-xs lg:inline">{user?.email}</span>
              <button onClick={logout} className="border-base rounded-lg border px-3 py-1.5 text-xs font-medium transition hover:text-red-600">
                Salir
              </button>
            </div>
          </header>
          <main className="mx-auto w-full max-w-7xl p-6 lg:p-8">{children}</main>
        </div>
      </div>
      </RequireAuth>
  );
}
