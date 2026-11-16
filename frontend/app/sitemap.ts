import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_SITE_URL || "https://mysecop.co";
  const now = new Date();
  return [
    { url: `${base}/`, lastModified: now, changeFrequency: "weekly", priority: 1 },
    { url: `${base}/contacto`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${base}/iniciar-sesion`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
    { url: `${base}/registro`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
  ];
}
