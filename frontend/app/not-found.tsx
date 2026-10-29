import Link from "next/link";

export default function NotFound() {
  return (
    <main className="hero-grid flex min-h-screen items-center justify-center px-5">
      <div className="surface-card shadow-card w-full max-w-md p-8 text-center">
        <p className="text-teal text-sm font-semibold">404</p>
        <h1 className="mt-2 text-2xl font-bold">Página no encontrada</h1>
        <p className="text-muted mt-3 text-sm">
          La dirección que intentaste abrir no existe o fue movida.
        </p>
        <Link href="/" className="text-teal mt-6 inline-block text-sm font-medium hover:underline">
          Volver al inicio
        </Link>
      </div>
    </main>
  );
}
