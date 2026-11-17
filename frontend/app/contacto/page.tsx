import Link from "next/link";
import { ContactForm } from "@/components/contact-form";

export default function Contacto() {
  return (
    <main className="hero-grid min-h-screen px-5 py-12 sm:py-16">
      <div className="mx-auto max-w-3xl">
        <Link href="/" className="mb-8 inline-flex items-center gap-2" aria-label="Volver al inicio de MySECOP">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-900 text-[10px] font-bold text-white dark:bg-teal dark:text-slate-950">MS</span>
          <span className="text-lg font-bold">MySECOP</span>
        </Link>
        <div className="surface-card shadow-card p-6 sm:p-8">
          <h1 className="text-2xl font-bold tracking-tight">Contáctanos</h1>
          <p className="text-muted mt-2 text-sm">Déjanos tus nombres, correo, teléfono y mensaje. También puedes escribirnos directamente por WhatsApp.</p>
          <ContactForm />
        </div>
      </div>
    </main>
  );
}
