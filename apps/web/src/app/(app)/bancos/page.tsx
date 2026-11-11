import type { Metadata } from "next";
import { QuestionBanksScreen } from "@/features/question-banks/question-banks-screen";

export const metadata: Metadata = { title: "Bancos de preguntas · Reclutamiento IA" };

export default function Page() {
  return <QuestionBanksScreen />;
}
