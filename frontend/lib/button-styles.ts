export function buttonStyles({ variant = "primary", size = "md", className = "" }: { variant?: "primary" | "outline" | "ghost" | "danger"; size?: "sm" | "md"; className?: string } = {}) {
  const base = "min-h-11 inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all duration-150 active:scale-[.98] disabled:opacity-50 disabled:cursor-not-allowed";
  const sizes = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2 text-sm" };
  const variants = {
    primary: "bg-brand-900 text-white shadow-sm hover:-translate-y-px hover:bg-brand-800 dark:bg-teal dark:text-slate-950 dark:hover:bg-teal-light",
    outline: "border border-base bg-[var(--surface)] hover:border-teal hover:bg-teal/5 dark:hover:bg-slate-800",
    ghost: "bg-transparent hover:bg-brand-50 dark:hover:bg-slate-800",
    danger: "bg-red-600 text-white hover:bg-red-700",
  };
  return `${base} ${sizes[size]} ${variants[variant]} ${className}`;
}
