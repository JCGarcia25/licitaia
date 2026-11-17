"use client";
import { useEffect, useState } from "react";
import SecopOpportunities from "@/components/secop-opportunities";
import { TvecQuotations } from "@/components/tvec-quotations";
import { TvecExplorer } from "@/components/tvec-explorer";
import { SourceSelector, Source } from "@/components/source-selector";
import { Spinner } from "@/components/ui";

export default function OpportunitiesPage() {
  const [source,setSource]=useState<Source>("secop");
  const [history,setHistory]=useState(false);
  const [ready,setReady]=useState(false);
  useEffect(() => {
    const restore=()=>{
      let params=new URLSearchParams(window.location.search);
      if (!params.toString()) {
        const saved=sessionStorage.getItem("mysecop_source_url");
        if (saved && saved.startsWith("/app/oportunidades?") && saved.length<5000) {
          window.history.replaceState(null,"",saved);params=new URLSearchParams(window.location.search);
        }
      }
      setHistory(params.get("tv_section")==="history");
      const value=params.get("fuente");setSource(value==="tvec" || value==="todas" ? value : "secop");setReady(true);
    };
    restore();window.addEventListener("popstate",restore);return()=>window.removeEventListener("popstate",restore);
  },[]);
  const change=(value:Source)=>{
    const url=new URL(window.location.href);url.searchParams.set("fuente",value);
    window.history.pushState(null,"",url.pathname+url.search);sessionStorage.setItem("mysecop_source_url",url.pathname+url.search);setSource(value);
  };
  if (!ready) return <Spinner label="Cargando fuentes…"/>;
  return <div className="space-y-6">
    <SourceSelector source={source} onChange={change}/>
    {source!=="tvec" && <section aria-label="Procesos SECOP"><p className="mb-3 text-sm font-semibold text-teal-dark dark:text-teal">Procesos SECOP</p><SecopOpportunities/></section>}
    {source!=="secop" && <section aria-label="Tienda Virtual" className="space-y-4"><div role="group" aria-label="Vista TVEC" className="flex flex-wrap gap-2">{([[false,"Cotizaciones vigentes"],[true,"Inteligencia de mercado · histórico"]] as const).map(([isHistory,label])=><button type="button" key={String(label)} aria-pressed={history===isHistory} className="min-h-11 rounded-lg border border-base px-4 py-2 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal" onClick={()=>{const url=new URL(window.location.href);url.searchParams.set("tv_section",isHistory?"history":"quotations");window.history.pushState(null,"",url.pathname+url.search);sessionStorage.setItem("mysecop_source_url",url.pathname+url.search);setHistory(Boolean(isHistory));}}>{history===isHistory?"✓ ":""}{label}</button>)}</div>{history?<TvecExplorer/>:<TvecQuotations/>}</section>}
  </div>;
}
