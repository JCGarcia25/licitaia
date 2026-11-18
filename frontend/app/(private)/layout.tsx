import { noIndex } from "@/lib/seo";
export const metadata = { title: "Mi cuenta", robots: noIndex };
export default function Layout({ children }: { children: React.ReactNode }) { return children; }
