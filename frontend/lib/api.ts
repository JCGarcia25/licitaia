"use client";
/* Cliente de la API LicitaIA con sesión JWT. */
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("licitaia_token");
}

export function setToken(token: string) {
  localStorage.setItem("licitaia_token", token);
}

export function clearToken() {
  localStorage.removeItem("licitaia_token");
}

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) };
  if (opts.body && !(opts.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API}${path}`, { ...opts, headers });
  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/iniciar-sesion")) {
      window.location.href = "/iniciar-sesion";
    }
    throw new Error("No autenticado");
  }
  if (!res.ok) {
    let detail = await res.text();
    try {
      const parsed = JSON.parse(detail);
      const raw = parsed.detail ?? parsed;
      if (Array.isArray(raw)) {
        detail = raw
          .map((item) => {
            const location = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : "";
            return location ? `${location}: ${item.msg || "Valor inválido"}` : (item.msg || JSON.stringify(item));
          })
          .join("; ");
      } else if (typeof raw === "object" && raw !== null) {
        detail = raw.message || JSON.stringify(raw);
      } else {
        detail = String(raw);
      }
    } catch {}
    throw new Error(detail || `Error ${res.status}`);
  }
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("application/json") ? res.json() : res.blob()) as Promise<T>;
}

export function descargarBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
