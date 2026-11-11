import type { Metadata } from "next";
import { ReportsScreen } from "@/features/reports/reports-screen";

export const metadata: Metadata = { title: "Indicadores y reportes · Reclutamiento IA" };

export default function Page() {
  return <ReportsScreen />;
}
