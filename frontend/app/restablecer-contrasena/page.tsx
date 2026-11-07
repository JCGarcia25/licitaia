"use client";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button, Field, Input } from "@/components/ui";

export default function RestablecerContrasena() {
  const [token, setToken] = useState("");
  useEffect(() => setToken(new URLSearchParams(window.location.search).get("token") || ""), []);
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [mostrar, setMostrar] = useState(false);
  async function enviar(event: FormEvent) {
    event.preventDefault();
    if (password !== confirmacion) return setMensaje("Las contraseñas no coinciden.");
    try { await api("/api/auth/reset-password", { method: "POST", body: JSON.stringify({ token, password }) }); setMensaje("Contraseña actualizada. Ya puedes iniciar sesión."); setTimeout(() => router.push("/iniciar-sesion"), 1200); }
    catch (error) { setMensaje(error instanceof Error ? error.message : "No fue posible actualizar la contraseña."); }
  }
  return <div className="hero-grid flex min-h-screen items-center justify-center px-5"><div className="surface-card w-full max-w-md p-8"><div className="mb-6 flex items-center gap-2"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-900 text-[10px] font-bold text-white dark:bg-teal dark:text-slate-950">MS</span><span className="text-lg font-bold">MySECOP</span></div><h1 className="text-xl font-bold">Restablecer contraseña</h1><p className="text-muted mt-1 text-sm">Crea una nueva contraseña segura para tu cuenta.</p><form onSubmit={enviar} className="mt-6 space-y-4"><Field label="Nueva contraseña"><Input required minLength={8} type={mostrar ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} /></Field><Field label="Confirmar contraseña"><Input required minLength={8} type={mostrar ? "text" : "password"} value={confirmacion} onChange={(e) => setConfirmacion(e.target.value)} /></Field><label className="text-muted flex items-center gap-2 text-xs"><input type="checkbox" checked={mostrar} onChange={(e) => setMostrar(e.target.checked)} className="accent-teal" /> Mostrar contraseñas</label><Button type="submit" className="w-full" disabled={!token}>Actualizar contraseña</Button></form>{mensaje ? <p className={`mt-4 text-sm ${mensaje.includes("actualizada") ? "text-teal" : "text-red-500"}`}>{mensaje}</p> : null}</div></div>;
}
