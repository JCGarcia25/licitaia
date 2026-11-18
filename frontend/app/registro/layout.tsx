import { noIndex } from "@/lib/seo";
export const metadata = { title: "Crear cuenta", robots: noIndex, alternates: { canonical: "/registro" } };

import { AuthProvider } from "@/components/auth";

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
