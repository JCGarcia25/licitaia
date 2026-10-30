"use client";
/* Componentes UI base (estilo shadcn/ui, implementación propia y ligera). */
import { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`surface-card shadow-card ${className}`}>{children}</div>;
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-base px-5 py-4">
      <div>
        <h3 className="text-sm font-semibold tracking-tight">{title}</h3>
        {subtitle ? <p className="text-muted mt-0.5 text-xs">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}

type ButtonProps = {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md";
  type?: "button" | "submit";
  disabled?: boolean;
  className?: string;
};

export function Button({ children, onClick, variant = "primary", size = "md", type = "button", disabled, className = "" }: ButtonProps) {
  const base = "inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all duration-150 active:scale-[.98] disabled:opacity-50 disabled:cursor-not-allowed";
  const sizes = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2 text-sm" };
  const variants = {
    primary: "bg-brand-900 text-white shadow-sm hover:-translate-y-px hover:bg-brand-800 dark:bg-teal dark:text-slate-950 dark:hover:bg-teal-light",
    outline: "border border-base bg-[var(--surface)] hover:border-teal hover:bg-teal/5 dark:hover:bg-slate-800",
    ghost: "bg-transparent hover:bg-brand-50 dark:hover:bg-slate-800",
    danger: "bg-red-600 text-white hover:bg-red-700",
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}>
      {children}
    </button>
  );
}

export function Badge({ children, tone = "blue" }: { children: ReactNode; tone?: "blue" | "teal" | "green" | "red" | "amber" | "gray" | "purple" }) {
  const tones: Record<string, string> = {
    blue: "bg-brand-50 text-brand-800 dark:bg-slate-800 dark:text-brand-300",
    teal: "bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300",
    green: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
    red: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300",
    amber: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
    purple: "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
    gray: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  };
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>{children}</span>;
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-lg border border-base bg-transparent px-3 py-2 text-sm outline-none transition focus:border-teal focus:ring-2 focus:ring-teal/20 ${props.className || ""}`}
    />
  );
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`w-full rounded-lg border border-base bg-transparent px-3 py-2 text-sm outline-none transition focus:border-teal focus:ring-2 focus:ring-teal/20 ${props.className || ""}`}
    />
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`w-full rounded-lg border border-base bg-transparent px-3 py-2 text-sm outline-none transition focus:border-teal focus:ring-2 focus:ring-teal/20 ${props.className || ""}`}
    />
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-muted">{label}</span>
      {children}
      {hint ? <span className="text-muted mt-1 block text-[11px]">{hint}</span> : null}
    </label>
  );
}

export function Spinner({ label = "Cargando…" }: { label?: string }) {
  return (
    <div className="text-muted flex items-center gap-2 py-8 text-sm">
      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-teal border-t-transparent" />
      {label}
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body?: string }) {
  return (
    <div className="py-10 text-center">
      <p className="text-sm font-medium">{title}</p>
      {body ? <p className="text-muted mt-1 text-xs">{body}</p> : null}
    </div>
  );
}

export function fmtCOP(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "N/D";
  return `$ ${new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(valor)} COP`;
}

export function fmtFecha(valor: string | null | undefined): string {
  if (!valor) return "N/D";
  const d = new Date(valor);
  if (isNaN(d.getTime())) return String(valor);
  return new Intl.DateTimeFormat("es-CO", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(d);
}

export function scoreTone(score: number | null | undefined): "green" | "amber" | "red" | "gray" {
  if (score === null || score === undefined) return "gray";
  if (score >= 70) return "green";
  if (score >= 45) return "amber";
  return "red";
}
