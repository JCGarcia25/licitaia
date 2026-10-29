import { AuthProvider } from "@/components/auth";

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
