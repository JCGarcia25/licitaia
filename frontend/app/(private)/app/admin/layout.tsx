"use client";

import { ReactNode, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/components/auth";
import { Spinner } from "@/components/ui";

const SUPER_ADMIN = "jorge@zorbagames.com";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const autorizado = user?.email?.trim().toLowerCase() === SUPER_ADMIN;

  useEffect(() => {
    if (user && !autorizado) router.replace("/app");
  }, [autorizado, router, user]);

  if (!user || !autorizado || !pathname.startsWith("/app/admin")) {
    return <Spinner label="Verificando permisos…" />;
  }
  return <>{children}</>;
}
