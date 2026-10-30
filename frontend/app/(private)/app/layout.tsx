"use client";
/* Estructura de la aplicación privada (barra lateral + topbar). */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import { AuthProvider, RequireAuth, useAuth } from "@/components/auth";
import { ThemeToggle } from "@/components/theme";

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

  return (
      <RequireAuth>
      <div className="flex min-h-screen">
        {/* Sidebar */}
        <aside className="hidden w-60 shrink-0 border-r border-base bg-[var(--surface)] md:block">
          <div className="flex h-16 items-center gap-2 border-b border-base px-5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-900 text-[9px] font-bold text-white dark:bg-teal dark:text-slate-950">MS</span>
            <span className="font-bold tracking-tight">MySECOP</span>
          </div>
          <nav className="space-y-1 p-3">
            {NAV.map((n) => {
              const activo = n.href === "/app" ? pathname === "/app" : pathname.startsWith(n.href);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                    activo
                      ? "bg-brand-50 font-medium text-brand-900 dark:bg-slate-800 dark:text-teal"
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
          <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-base bg-[var(--bg)]/85 px-5 backdrop-blur">
            <div className="flex items-center gap-4 overflow-x-auto md:hidden">
              {NAV.map((n) => (
                <Link key={n.href} href={n.href} className="text-muted whitespace-nowrap text-xs hover:text-teal">{n.label}</Link>
              ))}
            </div>
            <div className="hidden md:block" />
            <div className="flex items-center gap-3">
              <ThemeToggle />
              <span className="text-muted hidden text-xs sm:inline">{user?.email}</span>
              <button onClick={logout} className="border-base rounded-lg border px-3 py-1.5 text-xs font-medium transition hover:text-red-600">
                Salir
              </button>
            </div>
          </header>
          <main className="mx-auto max-w-6xl p-5">{children}</main>
        </div>
      </div>
      </RequireAuth>
  );
}
