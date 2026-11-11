import type { Metadata } from "next";
import { VacanciesScreen } from "@/features/vacancies/vacancies-screen";

export const metadata: Metadata = { title: "Vacantes · Reclutamiento IA" };

export default function Page() {
  return <VacanciesScreen />;
}
