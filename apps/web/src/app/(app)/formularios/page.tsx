import type { Metadata } from "next";
import { FormTemplatesScreen } from "@/features/form-templates/form-templates-screen";

export const metadata: Metadata = { title: "Formularios · Reclutamiento IA" };

export default function Page() {
  return <FormTemplatesScreen />;
}
