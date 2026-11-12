import type { Metadata } from "next";
import { StudyQueueScreen } from "@/features/studies/study-queue-screen";

export const metadata: Metadata = { title: "Estudios · Reclutamiento IA" };

export default function Page() {
  return <StudyQueueScreen />;
}
