import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ThemeInitScript } from "@/components/theme";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://mysecop.co"),
  title: {
    default: "MySECOP | Encuentra oportunidades de contratación pública",
    template: "%s | MySECOP",
  },
  description: "Encuentra, filtra y analiza oportunidades de contratación pública en SECOP II con inteligencia artificial. Mejora tus decisiones y compite con más información.",
  applicationName: "MySECOP",
  keywords: ["SECOP II", "licitaciones Colombia", "contratación pública", "oportunidades de negocio", "pliegos de condiciones", "Colombia Compra Eficiente"],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "es_CO",
    url: "/",
    siteName: "MySECOP",
    title: "MySECOP | Inteligencia para contratación pública",
    description: "Descubre oportunidades de SECOP II que encajan con tu empresa y analiza sus requisitos con evidencia.",
  },
  twitter: {
    card: "summary",
    title: "MySECOP | Inteligencia para contratación pública",
    description: "Encuentra oportunidades de SECOP II que encajan con tu empresa.",
  },
  robots: { index: true, follow: true, googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 } },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
        <ThemeInitScript />
      </head>
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
