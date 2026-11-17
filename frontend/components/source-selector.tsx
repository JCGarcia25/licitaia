"use client";
export type Source = "todas"|"secop"|"tvec";
export function SourceSelector({source,onChange}:{source:Source;onChange:(source:Source)=>void}) {
  return <div role="group" aria-label="Fuente de información" className="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap">
    {([["todas","Todas"],["secop","SECOP"],["tvec","Tienda Virtual"]] as const).map(([value,label]) =>
      <button key={value} type="button" aria-pressed={source===value} onClick={()=>onChange(value)}
        className={`min-h-11 rounded-lg border px-2 py-2 text-sm sm:px-4 font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-dark dark:focus-visible:outline-teal ${source===value ? "border-teal bg-teal/10 text-[var(--text)]" : "border-base bg-[var(--surface)] text-[var(--text)]"}`}>{source===value && <span aria-hidden="true">✓ </span>}{label}</button>)}
  </div>;
}
