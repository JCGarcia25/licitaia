import { ImageResponse } from "next/og";
export const alt = "MySECOP: oportunidades de contratación pública en Colombia";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export default function Image() {
  return new ImageResponse(<div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "center", padding: 80, background: "#071426", color: "#e8f0f9" }}>
    <div style={{ display: "flex", fontSize: 40, color: "#2dd4bf", marginBottom: 32 }}>MySECOP</div>
    <div style={{ display: "flex", fontSize: 64, fontWeight: 700, lineHeight: 1.15 }}>Oportunidades de contratación pública en Colombia</div>
    <div style={{ display: "flex", fontSize: 30, marginTop: 32 }}>Encuentra procesos. Analiza requisitos. Organiza tus ofertas.</div>
  </div>, size);
}
