import type { Metadata } from "next";
import "./globals.css";
import { ThemeInitScript } from "@/components/theme";
import { AuthProvider } from "@/components/auth";

export const metadata: Metadata = {
  title: "LicitaIA — La inteligencia detrás de tu próxima licitación",
  description:
    "LicitaIA encuentra las oportunidades de contratación pública que encajan con tu empresa, analiza sus requisitos y te ayuda a decidir dónde competir. No es una plataforma oficial del Gobierno colombiano.",
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
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
