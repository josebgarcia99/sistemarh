import type { NextConfig } from "next";

// En desarrollo, el navegador llama a /api en este mismo origen y Next.js lo
// reenvía a la API. En producción ese reenvío lo hace el proxy inverso.
// La variable es del servidor: nunca usar NEXT_PUBLIC_ para direcciones internas ni secretos.
const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

// Cabeceras de seguridad de las pantallas. Las respuestas de /api llevan las
// suyas, que fija la propia API.
// La política de contenido impide enmarcar la aplicación, cambiar la base de los
// enlaces, enviar formularios a otro sitio e incrustar complementos. No limita
// todavía el origen de los scripts: eso exige un valor de un solo uso por
// respuesta y debe probarse en el servidor real (ver docs/security/modelo_amenazas.md).
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  {
    key: "Content-Security-Policy",
    value: "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'",
  },
];

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
  async headers() {
    return [{ source: "/((?!api/).*)", headers: securityHeaders }];
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
