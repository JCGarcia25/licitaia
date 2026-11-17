"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiBackground as api } from "@/lib/api";
import { Button, Card } from "@/components/ui";

type RefreshState={state:'IDLE'|'PENDING'|'RUNNING'|'COOLDOWN'|'ERROR'|'UNCONFIRMED';pages:number;total_pages:number|null;retry_after:number;last_updated:string|null;accepted?:boolean};
const active=(s:RefreshState|null)=>!!s&&['PENDING','RUNNING','UNCONFIRMED'].includes(s.state);

export function TvecRefreshButton({onComplete}:{onComplete:()=>void}){
  const [status,setStatus]=useState<RefreshState|null>(null),[posting,setPosting]=useState(false),[error,setError]=useState('');
  const [clock,setClock]=useState(Date.now());const received=useRef(Date.now());
  const mounted=useRef(true),publishing=useRef(false),version=useRef(0),previous=useRef<RefreshState|null>(null);
  const completion=useRef(onComplete);completion.current=onComplete;
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;version.current++;};},[]);
  const accept=useCallback((value:RefreshState)=>{
    const wasActive=active(previous.current);previous.current=value;received.current=Date.now();
    setClock(Date.now());setStatus(value);setError('');
    if(wasActive&&!active(value)&&value.state!=='ERROR')completion.current();
  },[]);
  const read=useCallback(async()=>{
    if(publishing.current)return;const id=++version.current;
    try{const value=await api<RefreshState>('/api/tvec/quotations/refresh-status');if(mounted.current&&id===version.current)accept(value);}
    catch{if(mounted.current&&id===version.current)setError('No pudimos consultar el estado de actualización. Volveremos a intentarlo.');}
  },[accept]);
  const inProgress=active(status);
  useEffect(()=>{void read();const timer=window.setInterval(()=>void read(),inProgress?3000:30000);return()=>window.clearInterval(timer);},[read,inProgress]);
  useEffect(()=>{const timer=window.setInterval(()=>setClock(Date.now()),1000);return()=>window.clearInterval(timer);},[]);
  const request=async()=>{
    if(publishing.current)return;publishing.current=true;version.current++;setPosting(true);setError('');
    try{const value=await api<RefreshState>('/api/tvec/quotations/refresh',{method:'POST',body:'{}'});if(mounted.current)accept(value);}
    catch(e){if(mounted.current)setError(e instanceof Error?e.message:'No pudimos confirmar la solicitud de actualización.');}
    finally{publishing.current=false;if(mounted.current){setPosting(false);void read();}}
  };
  const wait=Math.max(0,(status?.retry_after||0)-Math.floor((clock-received.current)/1000));
  const remaining=`${Math.floor(wait/60)}:${String(wait%60).padStart(2,'0')}`;
  return <Card className="p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div className="min-w-0 text-sm"><p>Solicita una revisión de la fuente oficial. La actualización es compartida y conserva tus filtros.</p>
      <p className="text-muted mt-2" role="status" aria-live="polite">
        {status?.state==='RUNNING'?`Recorrido en curso: ${status.pages} de ${status.total_pages??'…'} páginas. Se reutiliza la actualización compartida.`:
         status?.state==='PENDING'?'Solicitud recibida. La actualización comenzará en breve.':
         status?.state==='UNCONFIRMED'?'El envío aún no está confirmado. Estamos consultando el estado antes de permitir otro intento.':
         status?.state==='ERROR'?'La actualización no terminó. Conservamos la publicación anterior y el avance para reanudarla.':
         wait>0?'La última actualización es reciente.':'La actualización automática continúa cada 15 minutos.'}
      </p>{wait>0&&!inProgress&&<p className="text-muted mt-1 text-xs">Podrás solicitar otra actualización en {remaining}.</p>}
    </div>
    <Button className="min-h-11 shrink-0" variant="outline" disabled={posting||inProgress||wait>0} onClick={()=>void request()}>{posting?'Solicitando actualización…':inProgress?'Actualización en curso':'Actualizar cotizaciones TVEC'}</Button>
  </div>{error&&<p className="mt-3 text-sm" role="alert">{error}</p>}</Card>;
}
