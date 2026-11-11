import type { Metadata } from "next";
import "@fontsource-variable/outfit";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Reclutamiento IA",
  description: "Sistema Integral de Reclutamiento e Inteligencia Artificial",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
