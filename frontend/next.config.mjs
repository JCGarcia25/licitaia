/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },
  reactStrictMode: true,
  async headers() {
    const origin = new URL(process.env.NEXT_PUBLIC_SITE_URL || process.env.NEXT_PUBLIC_API_URL || "https://mysecop.co");
    const productionSite = process.env.NODE_ENV === "production" && origin.hostname === "mysecop.co";
    const excluded = ["/app/:path*", "/api/:path*", "/iniciar-sesion", "/registro", "/restablecer-contrasena", "/verificar-correo", "/legal/:path*"];
    return (productionSite ? excluded : ["/:path*"]).map(source => ({ source, headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] }));
  },
};

export default nextConfig;
