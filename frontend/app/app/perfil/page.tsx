"use client";
/* Perfil empresarial: alimentación directa del Cazador de Oportunidades. */
import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button, Card, CardHeader, Field, Input, Select, Spinner, Textarea } from "@/components/ui";

type Profile = {
  nombre_comercial: string; razon_social: string; nit: string; sector: string;
  actividades: string; productos_servicios: string; keywords: string[]; unspsc_codes: string[];
  departamentos: string[]; municipios: string[]; presupuesto_min: number | null; presupuesto_max: number | null;
  modalidades: string[]; experiencia: string; capacidades: string; certificaciones: string[]; acepta_consorcios: boolean;
};

const VACIO: Profile = {
  nombre_comercial: "", razon_social: "", nit: "", sector: "", actividades: "", productos_servicios: "",
  keywords: [], unspsc_codes: [], departamentos: [], municipios: [], presupuesto_min: null, presupuesto_max: null,
  modalidades: [], experiencia: "", capacidades: "", certificaciones: [], acepta_consorcios: false,
};

const DEPARTAMENTOS = ["Amazonas", "Antioquia", "Arauca", "Atlántico", "Bogotá D.C.", "Bolívar", "Boyacá", "Caldas", "Caquetá", "Casanare", "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca", "Huila", "La Guajira", "Magdalena", "Meta", "Nariño", "Norte de Santander", "Putumayo", "Quindío", "Risaralda", "Santander", "Sucre", "Tolima", "Valle del Cauca"];
const MODALIDADES = ["Licitación Pública", "Contratación Directa", "Contratación Mínima Cuantía", "Selección Abreviada", "Concurso de Méritos", "Régimen Especial", "Subasta", "Acuerdo Marco de Precio"];

export default function Perfil() {
  const [p, setP] = useState<Profile | null>(null);
  const [msg, setMsg] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    api<Profile | null>("/api/profile")
      .then((r) => setP(r || VACIO))
      .catch(() => setP(VACIO));
  }, []);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (!p) return;
    setGuardando(true);
    setMsg("");
    try {
      await api("/api/profile", { method: "PUT", body: JSON.stringify(p) });
      setMsg("Perfil guardado. Ejecuta el agente en Oportunidades para re-puntuar.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Error guardando");
    } finally {
      setGuardando(false);
    }
  }

  const lista = (v: string) => v.split(",").map((s) => s.trim()).filter(Boolean);
  const texto = (arr: string[] | undefined) => (arr || []).join(", ");
  const num = (v: string) => (v === "" ? null : Number(v.replace(/[^\d.]/g, "")));

  if (!p) return <Spinner />;

  return (
    <form onSubmit={guardar} className="space-y-5">
      <div>
        <h1 className="text-xl font-bold tracking-tight">Perfil de la empresa</h1>
        <p className="text-muted text-sm">Estos datos alimentan al Cazador de Oportunidades. A mayor detalle, mejores coincidencias.</p>
      </div>

      <Card>
        <CardHeader title="Identificación" />
        <div className="grid gap-4 p-5 md:grid-cols-3">
          <Field label="Nombre comercial"><Input value={p.nombre_comercial} onChange={(e) => setP({ ...p, nombre_comercial: e.target.value })} /></Field>
          <Field label="Razón social"><Input value={p.razon_social} onChange={(e) => setP({ ...p, razon_social: e.target.value })} /></Field>
          <Field label="NIT"><Input value={p.nit} onChange={(e) => setP({ ...p, nit: e.target.value })} placeholder="900.123.456-7" /></Field>
          <Field label="Sector económico"><Input value={p.sector} onChange={(e) => setP({ ...p, sector: e.target.value })} placeholder="Tecnologías de la información" /></Field>
          <div className="md:col-span-2">
            <Field label="Certificaciones" hint="Separadas por coma: ISO 9001, ISO 14001…">
              <Input value={texto(p.certificaciones)} onChange={(e) => setP({ ...p, certificaciones: lista(e.target.value) })} />
            </Field>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Qué hace la empresa" subtitle="El agente usa este texto para la búsqueda semántica" />
        <div className="grid gap-4 p-5 md:grid-cols-2">
          <Field label="Actividades principales"><Textarea rows={3} value={p.actividades} onChange={(e) => setP({ ...p, actividades: e.target.value })} /></Field>
          <Field label="Productos y servicios"><Textarea rows={3} value={p.productos_servicios} onChange={(e) => setP({ ...p, productos_servicios: e.target.value })} /></Field>
          <Field label="Palabras clave" hint="Separadas por coma.">
            <Input value={texto(p.keywords)} onChange={(e) => setP({ ...p, keywords: lista(e.target.value) })} placeholder="desarrollo de software, interoperabilidad" />
          </Field>
          <Field label="Códigos UNSPSC" hint="Separados por coma: 81101500, 81112000…">
            <Input value={texto(p.unspsc_codes)} onChange={(e) => setP({ ...p, unspsc_codes: lista(e.target.value) })} />
          </Field>
        </div>
      </Card>

      <Card>
        <CardHeader title="Dónde y cuánto" />
        <div className="grid gap-4 p-5 md:grid-cols-2">
          <Field label="Departamentos de interés" hint="Separados por coma.">
            <Input value={texto(p.departamentos)} onChange={(e) => setP({ ...p, departamentos: lista(e.target.value) })} placeholder="Bogotá D.C., Cundinamarca" />
          </Field>
          <Field label="Municipios de interés"><Input value={texto(p.municipios)} onChange={(e) => setP({ ...p, municipios: lista(e.target.value) })} /></Field>
          <Field label="Presupuesto mínimo (COP)"><Input value={p.presupuesto_min ?? ""} onChange={(e) => setP({ ...p, presupuesto_min: num(e.target.value) })} placeholder="100000000" /></Field>
          <Field label="Presupuesto máximo (COP)"><Input value={p.presupuesto_max ?? ""} onChange={(e) => setP({ ...p, presupuesto_max: num(e.target.value) })} placeholder="5000000000" /></Field>
          <Field label="Modalidades preferidas" hint="Separadas por coma.">
            <Input value={texto(p.modalidades)} onChange={(e) => setP({ ...p, modalidades: lista(e.target.value) })} placeholder="Licitación Pública, Contratación Directa" />
          </Field>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={p.acepta_consorcios} onChange={(e) => setP({ ...p, acepta_consorcios: e.target.checked })} className="accent-teal" />
              Interés en consorcios o uniones temporales
            </label>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Capacidades" />
        <div className="grid gap-4 p-5 md:grid-cols-2">
          <Field label="Experiencia contractual"><Textarea rows={3} value={p.experiencia} onChange={(e) => setP({ ...p, experiencia: e.target.value })} placeholder="10 años en proyectos públicos de…" /></Field>
          <Field label="Capacidades operativas"><Textarea rows={3} value={p.capacidades} onChange={(e) => setP({ ...p, capacidades: e.target.value })} placeholder="Equipo de 30 ingenieros; capacidad financiera…" /></Field>
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar perfil"}</Button>
        {msg ? <p className="text-muted text-xs">{msg}</p> : null}
      </div>
    </form>
  );
}
