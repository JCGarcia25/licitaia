"use client";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Card, Badge, Spinner } from "@/components/ui";
import { TvecOrder, tvecDate, tvecAmount } from "@/components/tvec-explorer";

export default function TvecDetail(){
  const {id}=useParams<{id:string}>();const params=useSearchParams();const candidate=params.get('volver');
  const back=candidate?.startsWith('/app/oportunidades?')&&candidate.length<5000?candidate:'/app/oportunidades?fuente=tvec&tv_section=history';
  const [order,setOrder]=useState<TvecOrder|null>(null),[error,setError]=useState('');
  useEffect(()=>{let active=true;api<{order:TvecOrder}>('/api/tvec/orders/'+encodeURIComponent(id)).then(r=>{if(active)setOrder(r.order);}).catch(e=>{if(active)setError(e instanceof Error?e.message:'No se pudo consultar la orden.');});return()=>{active=false;};},[id]);
  return <div className="space-y-4"><Link href={back} className="inline-flex min-h-11 items-center text-sm text-teal-dark dark:text-teal underline">← Volver a compras y fuentes</Link>
    {error?<Card className="p-4 sm:p-5"><p role="alert">{error}</p></Card>:!order?<Spinner label="Consultando orden de compra…"/>:<Card className="p-4 sm:p-5"><Badge tone="teal">Orden de compra TVEC</Badge><h1 className="mt-3 break-words text-xl font-bold">Orden {order.official_id}</h1><p className="text-muted mt-3 text-sm">Compra registrada para inteligencia comercial. No es una convocatoria abierta. Participación por verificar.</p>
      <p className="mt-4 whitespace-pre-wrap break-words text-sm">{order.description||'La fuente no informa descripción.'}</p>
      <dl className="mt-6 grid gap-4 sm:grid-cols-2">{[['Entidad compradora',order.buyer],['Proveedor registrado',order.supplier],['Instrumento de compra',order.instrument],['Actividad del proveedor',order.category],['Departamento',order.department],['Ciudad o municipio',order.city],['Valor registrado',tvecAmount(order.amount)],['Estado del registro',order.status],['Fecha de orden',tvecDate(order.issued_at)],['Vencimiento de la orden (no plazo para ofertar)',tvecDate(order.expires_at)],['Última sincronización local',tvecDate(order.synced_at)]].map(([label,value])=><div key={label}><dt className="text-muted text-xs">{label}</dt><dd className="mt-1 break-words text-sm">{value||'No informado'}</dd></div>)}</dl>
      <p className="text-muted mt-6 text-sm">La fuente no permite verificar la vigencia del instrumento ni la habilitación para cotizar. Los ítems se muestran tal como están descritos, sin inventar cantidades, precios unitarios o líneas de producto.</p>
      <a href={order.source_url} target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex min-h-11 items-center text-sm font-semibold text-teal-dark dark:text-teal underline">Ver dataset oficial TVEC (nueva pestaña)</a>
    </Card>}
  </div>;
}
