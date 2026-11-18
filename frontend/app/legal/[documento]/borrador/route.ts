import drafts from "@/lib/legal-drafts.json";

// Review copies are served only by the DEV frontend build.
export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{ documento: string }> }) {
  if (process.env.NEXT_PUBLIC_API_URL !== "https://dev.mysecop.co") {
    return new Response("No encontrado", { status: 404 });
  }
  const { documento } = await params;
  if (!Object.hasOwn(drafts, documento)) return new Response("No encontrado", { status: 404 });
  const draft = drafts[documento as keyof typeof drafts];
  return new Response(draft.content, { headers: {
    "Content-Type": "text/markdown; charset=utf-8",
    "Content-Disposition": `attachment; filename="BORRADOR_${draft.filename}"`,
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Robots-Tag": "noindex, nofollow",
  } });
}
