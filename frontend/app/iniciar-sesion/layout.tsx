import { noIndex } from "@/lib/seo";
export const metadata = { title: "Iniciar sesión", robots: noIndex, alternates: { canonical: "/iniciar-sesion" } };

import { AuthProvider } from "@/components/auth";

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
