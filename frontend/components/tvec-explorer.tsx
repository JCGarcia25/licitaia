"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Badge, Button, Card, Field, Input, Spinner } from "@/components/ui";

export type TvecOrder={id:number;official_id:string;buyer:string|null;supplier:string|null;description:string|null;instrument:string|null;category:string|null;department:string|null;city:string|null;amount:string|null;currency:string|null;issued_at:string|null;expires_at:string|null;status:string|null;synced_at:string;version:string;source_url:string;official_url:string|null};
type Provenance={source_updated_at:string|null;last_complete_at:string|null;local_orders:number;source_count_at_check:number|null;coverage_note:string;currency_note:string};
type Group={name:string;orders:number;first_order:string|null;last_order:string|null;buyers:number;suppliers:number;categories:number};
type Summary={orders:number;orders_with_value:number;buyers:number;suppliers:number;periods:{period:string;orders:number}[];provenance:Provenance};
type Result={items:(TvecOrder|Group)[];total:number;provenance:Provenance};
const FILTERS=[['buyer','Entidad compradora (nombre exacto)'],['supplier','Proveedor (nombre exacto)'],['instrument','Instrumento (nombre exacto)'],['category','Actividad del proveedor (texto exacto)'],['department','Departamento (nombre exacto)'],['city','Municipio o ciudad (nombre exacto)'],['status','Estado del registro (texto exacto)'],['amount_min','Valor mínimo registrado'],['amount_max','Valor máximo registrado'],['date_from','Desde (fecha de orden)'],['date_to','Hasta (fecha de orden)']] as const;
type Filter=Record<string,string>;
const empty:Filter=Object.fromEntries(['q',...FILTERS.map(([k])=>k)].map(k=>[k,'']));
export const tvecDate=(value:string|null)=>value ? new Intl.DateTimeFormat('es-CO',{timeZone:'UTC'}).format(new Date(value)) : 'No informada';
export const tvecAmount=(value:string|null)=>{
  if(value===null)return 'Valor no informado';
  const [whole,fraction='']=value.split('.');
  const decimals=fraction.replace(/0+$/,'');
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g,'.')}${decimals?','+decimals:''} · moneda no informada`;
};

export function TvecExplorer(){
  const [draft,setDraft]=useState<Filter>(empty),[active,setActive]=useState<Filter>(empty);
  const [page,setPage]=useState(1),[view,setView]=useState('orders'),[ready,setReady]=useState(false);
  const [result,setResult]=useState<Result|null>(null),[summary,setSummary]=useState<Summary|null>(null);
  const [error,setError]=useState(''),[loading,setLoading]=useState(false);const request=useRef(0);
  useEffect(()=>{
    const restore=()=>{const p=new URLSearchParams(window.location.search);const values=Object.fromEntries(Object.keys(empty).map(k=>[k,p.get('tv_'+k)||'']));setDraft(values);setActive(values);setPage(Math.max(1,Math.min(5001,Number(p.get('tv_page'))||1)));const v=p.get('tv_view');setView(['buyers','suppliers','instruments','trends'].includes(v||'')?v!:'orders');setReady(true);};
    restore();window.addEventListener('popstate',restore);return()=>{request.current++;window.removeEventListener('popstate',restore);};
  },[]);
  const load=useCallback(async()=>{
    if(!ready)return;const version=++request.current;setLoading(true);setError('');
    const params=new URLSearchParams();Object.entries(active).forEach(([k,v])=>{if(v)params.set(k,v);});
    params.set('limit','20');params.set('offset',String((page-1)*20));
    try{
      const [s,r]=await Promise.all([api<Summary>('/api/tvec/summary?'+params),view==='trends'?Promise.resolve(null):api<Result>('/api/tvec/'+view+'?'+params)]);
      if(version===request.current){setSummary(s);setResult(r);}
    }catch(e){if(version===request.current){setError(e instanceof Error?e.message:'No fue posible consultar TVEC.');setResult(null);setSummary(null);}}
    finally{if(version===request.current)setLoading(false);}
  },[ready,active,page,view]);
  useEffect(()=>{void load();},[load]);
  const navigate=(values:Filter,next:number,kind=view)=>{
    const url=new URL(window.location.href);Array.from(url.searchParams.keys()).filter(k=>k.startsWith('tv_')&&k!=='tv_section').forEach(k=>url.searchParams.delete(k));
    Object.entries(values).forEach(([k,v])=>{if(v)url.searchParams.set('tv_'+k,v);});url.searchParams.set('tv_page',String(next));url.searchParams.set('tv_view',kind);
    window.history.pushState(null,'',url.pathname+url.search);sessionStorage.setItem('mysecop_source_url',url.pathname+url.search);setActive({...values});setPage(next);setView(kind);
  };
  return <div className="space-y-4">
    <div><h1 className="text-xl font-bold">Compras registradas en la Tienda Virtual del Estado Colombiano</h1><p className="text-muted mt-2 text-sm">Historial de compras para analizar demanda pública. Una orden de compra no es una convocatoria abierta. Participación por verificar.</p></div>
    <Card className="p-4">
      <form onSubmit={e=>{e.preventDefault();navigate(draft,1);}} className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row"><div className="min-w-0 flex-1"><Field label="Buscar compras TVEC"><Input maxLength={200} value={draft.q} onChange={e=>setDraft({...draft,q:e.target.value})} placeholder="Orden, descripción, entidad o proveedor"/></Field></div><Button type="submit" className="min-h-11 sm:self-end">Buscar compras</Button></div>
        <details className="rounded-lg border border-base p-3"><summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-dark dark:focus-visible:outline-teal">Filtros TVEC</summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{FILTERS.map(([k,label])=><Field key={k} label={label}><Input maxLength={k.startsWith('date')?undefined:255} type={k.startsWith('date')?'date':k.startsWith('amount')?'number':'text'} step={k.startsWith('amount')?'any':undefined} value={draft[k]} onChange={e=>setDraft({...draft,[k]:e.target.value})}/></Field>)}</div>
          <p className="text-muted mt-3 text-xs">Los filtros no se retiran cuando no hay resultados. Los valores no tienen moneda informada por la fuente.</p>
          <div className="mt-3 flex flex-wrap gap-2"><Button type="submit" className="min-h-11">Aplicar filtros TVEC</Button><Button variant="outline" className="min-h-11" onClick={()=>{setDraft(empty);navigate(empty,1);}}>Limpiar filtros TVEC</Button></div>
        </details>
      </form>
    </Card>
    <div role="group" aria-label="Analizar demanda TVEC" className="flex flex-wrap gap-2">{[['orders','Órdenes'],['buyers','Compradores'],['suppliers','Proveedores'],['instruments','Instrumentos'],['trends','Periodos']].map(([key,label])=><button type="button" key={key} aria-pressed={view===key} onClick={()=>navigate(active,1,key)} className={`min-h-11 rounded-lg border px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-dark dark:focus-visible:outline-teal ${view===key?'border-teal bg-teal/10':'border-base'}`}>{label}</button>)}</div>
    {loading?<div role="status"><Spinner label="Consultando compras TVEC…"/></div>:error?<Card className="p-4 sm:p-5"><p role="alert" className="text-sm">No pudimos consultar las compras TVEC. {error}</p><Button variant="outline" className="mt-3 min-h-11" onClick={()=>void load()}>Reintentar consulta</Button></Card>:<>
      {summary&&<Card className="p-4 sm:p-5"><div className="grid grid-cols-2 gap-4 sm:grid-cols-4">{[[summary.orders,'Compras filtradas'],[summary.buyers,'Entidades'],[summary.suppliers,'Proveedores registrados'],[summary.orders_with_value,'Compras con valor']].map(([n,label])=><div key={label}><p className="text-xl font-bold">{n}</p><p className="text-muted text-xs">{label}</p></div>)}</div><p className="text-muted mt-3 text-xs">Datos locales · Fuente actualizada: {tvecDate(summary.provenance.source_updated_at)}.</p><details className="mt-2"><summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold">Actualización y alcance de los datos</summary><p className="text-muted mt-2 text-xs">Órdenes almacenadas: {summary.provenance.local_orders}. Filas declaradas por la fuente: {summary.provenance.source_count_at_check??'sin verificar'}. Última reconciliación completa: {tvecDate(summary.provenance.last_complete_at)}. Actualización de la fuente: {tvecDate(summary.provenance.source_updated_at)}.</p><p className="text-muted mt-2 text-xs">Indicadores sobre las órdenes locales disponibles; agrupaciones por nombre registrado. La fuente no informa moneda: no se agregan valores monetarios ni se garantiza demanda futura. La vigencia del instrumento y la habilitación de proveedores no están verificadas.</p></details></Card>}
      {view==='trends'?<Card className="p-4 sm:p-5"><h2 className="font-semibold">Compras por periodo registrado</h2><p className="text-muted mt-1 text-xs">Conteos históricos de los últimos 12 periodos con registros locales; no son una proyección ni permiten inferir crecimiento con cobertura parcial.</p><ul className="mt-3 space-y-2">{summary?.periods.map(p=><li key={p.period} className="flex justify-between gap-4 text-sm"><span>{p.period}</span><span>{p.orders} compras</span></li>)}</ul>{!summary?.periods.length&&<p className="mt-3 text-sm">No hay fechas suficientes para mostrar periodos.</p>}</Card>:
        result?.items.length?<div className="grid gap-4 lg:grid-cols-2">{result.items.map(item=>view==='orders'?<TvecCard key={(item as TvecOrder).id} order={item as TvecOrder}/>:<Card key={(item as Group).name}><h2 className="break-words font-semibold">{(item as Group).name}</h2><p className="mt-2 text-sm">{(item as Group).orders} compras registradas · {(item as Group).categories} actividades · {(item as Group).buyers} entidades · {(item as Group).suppliers} proveedores</p><p className="text-muted mt-2 text-xs">{tvecDate((item as Group).first_order)} – {tvecDate((item as Group).last_order)}. Participación y vigencia por verificar.</p><Button className="mt-3 min-h-11" variant="outline" onClick={()=>{const key=view==='buyers'?'buyer':view==='suppliers'?'supplier':'instrument';const values={...active,[key]:(item as Group).name};setDraft(values);navigate(values,1,'orders');}}>Ver compras registradas</Button></Card>)}</div>:<Card className="p-4 sm:p-5"><h2 className="font-semibold">No hay compras que coincidan con estos filtros</h2><p className="text-muted mt-2 text-sm">Puedes modificar los filtros. Si aún no se han sincronizado órdenes, los indicadores no representan el dataset completo.</p></Card>}
      {view!=='trends'&&result&&<div className="flex flex-wrap items-center justify-between gap-3 text-sm" aria-label="Paginación TVEC"><p aria-live="polite">{result.total} resultados · Página {page} de {Math.max(1,Math.ceil(result.total/20))}</p><div className="flex gap-2"><Button variant="outline" className="min-h-11" disabled={page<=1} onClick={()=>navigate(active,page-1)}>Anterior TVEC</Button><Button variant="outline" className="min-h-11" disabled={page*20>=result.total} onClick={()=>navigate(active,page+1)}>Siguiente TVEC</Button></div></div>}
    </>}
  </div>;
}

function TvecCard({order}:{order:TvecOrder}){
  const back=typeof window==='undefined'?'/app/oportunidades?fuente=tvec&tv_section=history':window.location.pathname+window.location.search;
  return <Card className="p-4 sm:p-5"><Badge tone="teal">Orden de compra TVEC</Badge><h2 className="mt-3 break-words font-semibold"><Link className="hover:text-teal-dark dark:text-teal" href={`/app/tienda-virtual/${order.id}?volver=${encodeURIComponent(back)}`}>Orden {order.official_id}</Link></h2><p className="mt-2 whitespace-pre-wrap break-words text-sm">{order.description||'Descripción no informada'}</p><dl className="mt-4 space-y-2 text-sm">{[['Entidad compradora',order.buyer],['Proveedor registrado',order.supplier],['Instrumento de compra',order.instrument],['Actividad del proveedor',order.category],['Ubicación',[order.department,order.city].filter(Boolean).join(' · ')],['Valor registrado',tvecAmount(order.amount)],['Fecha de orden',tvecDate(order.issued_at)],['Estado del registro',order.status]].map(([label,value])=><div key={label}><dt className="text-muted text-xs">{label}</dt><dd className="break-words">{value||'No informado'}</dd></div>)}</dl><p className="text-muted mt-4 text-xs">Compra registrada · Participación por verificar. No es una solicitud de cotización abierta.</p><Link href={`/app/tienda-virtual/${order.id}?volver=${encodeURIComponent(back)}`} className="mt-3 inline-flex min-h-11 items-center text-sm font-semibold text-teal-dark dark:text-teal underline">Ver detalle de compra</Link></Card>;
}
