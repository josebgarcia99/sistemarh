import type { NextConfig } from "next";

// En desarrollo, el navegador llama a /api en este mismo origen y Next.js lo
// reenvía a la API. En producción ese reenvío lo hace el proxy inverso.
// La variable es del servidor: nunca usar NEXT_PUBLIC_ para direcciones internas ni secretos.
const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  experimental: {
    // El reenvío a la API debe dejar pasar una carga completa. El límite real
    // (20 MB por omisión) lo aplica la API; aquí va con margen.
    proxyClientMaxBodySize: "25mb",
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiInternalUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
