import type { Metadata } from "next";

// Deployments already pass NEXT_PUBLIC_API_URL at build time. Use it to keep
// preview environments out of search even when SITE_URL is not configured.
export const siteUrl = new URL(process.env.NEXT_PUBLIC_SITE_URL || process.env.NEXT_PUBLIC_API_URL || "https://mysecop.co").origin;
export const indexPublicPages = process.env.NODE_ENV === "production" && new URL(siteUrl).hostname === "mysecop.co";
export const noIndex: Metadata["robots"] = { index: false, follow: false };

export function publicMetadata(path: string, title: string, description: string): Metadata {
  return {
    title: { absolute: `${title} | MySECOP` }, description,
    alternates: { canonical: path },
    robots: indexPublicPages ? { index: true, follow: true } : noIndex,
    openGraph: { type: "website", locale: "es_CO", siteName: "MySECOP", title: `${title} | MySECOP`, description, url: path, images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MySECOP: contratación pública en Colombia" }] },
    twitter: { card: "summary_large_image", title: `${title} | MySECOP`, description, images: ["/opengraph-image"] },
  };
}
