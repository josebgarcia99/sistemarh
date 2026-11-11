import type { Metadata } from "next";
import { AiSettingsScreen } from "@/features/ai/ai-settings-screen";

export const metadata: Metadata = { title: "Configuración de IA · Reclutamiento IA" };

export default function Page() {
  return <AiSettingsScreen />;
}
