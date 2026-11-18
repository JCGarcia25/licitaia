import Link from "next/link";
import { noIndex } from "@/lib/seo";
export async function generateMetadata({ params }: { params: Promise<{ documento: string }> }) {
  const { documento } = await params;
  return { title: Object.hasOwn(LEGAL_DOCUMENTS, documento) ? LEGAL_DOCUMENTS[documento as keyof typeof LEGAL_DOCUMENTS] : "Documento no encontrado", robots: noIndex, alternates: { canonical: `/legal/${documento}` } };
}
import { notFound } from "next/navigation";
import { LEGAL_DOCUMENTS } from "../documents";
import { buttonStyles } from "@/lib/button-styles";

export function generateStaticParams() {
  return Object.keys(LEGAL_DOCUMENTS).map(documento => ({ documento }));
}

export default async function LegalDocument({ params }: { params: Promise<{ documento: string }> }) {
  const { documento } = await params;
  if (!Object.hasOwn(LEGAL_DOCUMENTS, documento)) notFound();
  const title = LEGAL_DOCUMENTS[documento as keyof typeof LEGAL_DOCUMENTS];
  return <main className="hero-grid min-h-[100svh] px-4 py-10 sm:py-16">
    <div className="mx-auto max-w-2xl">
      <Link href="/" className="mb-6 inline-flex min-h-11 items-center text-sm font-semibold text-teal underline">Volver al inicio de MySECOP</Link>
      <article className="surface-card space-y-5 p-5 sm:p-8">
        <h1 className="text-2xl font-bold">{title}</h1>
        <p className="leading-relaxed">Este documento todavía no está disponible para consulta en esta página.</p>
        <p className="text-muted leading-relaxed">Para solicitar la versión vigente o resolver una consulta sobre este tema, escríbenos a través del formulario de Contacto. Indica el nombre del documento en tu mensaje.</p>
        {process.env.NEXT_PUBLIC_API_URL === "https://dev.mysecop.co" && <div className="space-y-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
          <h2 className="font-semibold">Borrador para revisión en DEV</h2>
          <p className="text-sm leading-relaxed">Versión no vigente. Contiene campos pendientes y no constituye la política definitiva de MySECOP.</p>
          <a href={`/legal/${documento}/borrador`} className={buttonStyles({ variant: "outline", className: "text-[var(--text)]" })}>Descargar borrador no vigente</a>
        </div>}
        <Link href="/contacto" className={buttonStyles()}>Solicitar el documento por Contacto</Link>
      </article>
    </div>
  </main>;
}
