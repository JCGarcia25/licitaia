"use client";
import { useEffect, useState } from "react";
import SecopOpportunities from "@/components/secop-opportunities";
import { TvecExplorer } from "@/components/tvec-explorer";
import { SourceSelector, Source } from "@/components/source-selector";
import { Spinner } from "@/components/ui";

export default function OpportunitiesPage() {
  const [source,setSource]=useState<Source>("secop");
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
    {source!=="secop" && <section aria-label="Compras registradas TVEC"><TvecExplorer/></section>}
  </div>;
}
