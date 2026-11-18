import type { MetadataRoute } from "next";
import { indexPublicPages, siteUrl } from "@/lib/seo";

export default function sitemap(): MetadataRoute.Sitemap {
  if (!indexPublicPages) return [];
  // Only canonical public content. Do not invent a lastModified timestamp on
  // every request or include private screens, account forms or legal placeholders.
  return [
    { url: `${siteUrl}/`, changeFrequency: "weekly", priority: 1 },
    { url: `${siteUrl}/contacto`, changeFrequency: "monthly", priority: 0.6 },
  ];
}
