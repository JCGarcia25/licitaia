import type { Metadata } from "next";
import "./globals.css";
import { ThemeInitScript } from "@/components/theme";

export const metadata: Metadata = {
  title: "MySECOP — Inteligencia para contratación pública",
  description:
    "MySECOP encuentra oportunidades de contratación pública que encajan con tu empresa y analiza sus requisitos. No es una plataforma oficial del Gobierno colombiano.",
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
