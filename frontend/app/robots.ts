import type { MetadataRoute } from "next";
import { indexPublicPages, siteUrl } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  // Crawlers must be able to read noindex headers/meta on preview and account
  // pages; blocking these URLs here would hide their indexing instructions.
  if (!indexPublicPages) return { rules: [{ userAgent: "*", allow: "/", disallow: "/api" }] };
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/api"] }],
    sitemap: `${siteUrl}/sitemap.xml`, host: siteUrl,
  };
}
