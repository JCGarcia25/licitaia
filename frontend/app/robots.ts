import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const base = process.env.NEXT_PUBLIC_SITE_URL || "https://mysecop.co";
  return {
    rules: [{ userAgent: "*", allow: ["/", "/contacto", "/registro", "/iniciar-sesion"], disallow: ["/app", "/api", "/restablecer-contrasena"] }],
    sitemap: `${base}/sitemap.xml`,
    host: base,
  };
}
