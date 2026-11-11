import type { NextConfig } from "next";

// En desarrollo, el navegador llama a /api en este mismo origen y Next.js lo
// reenvía a la API. En producción ese reenvío lo hace el proxy inverso.
// La variable es del servidor: nunca usar NEXT_PUBLIC_ para direcciones internas ni secretos.
const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
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
