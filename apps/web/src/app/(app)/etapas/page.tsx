import type { Metadata } from "next";
import { PipelineScreen } from "@/features/pipeline/pipeline-screen";

export const metadata: Metadata = { title: "Etapas del proceso · Reclutamiento IA" };

export default function Page() {
  return <PipelineScreen />;
}
