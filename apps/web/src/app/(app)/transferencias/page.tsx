import type { Metadata } from "next";
import { MassTransferScreen } from "@/features/transfers/mass-transfer-screen";

export const metadata: Metadata = { title: "Baja con transferencia · Reclutamiento IA" };

export default function Page() {
  return <MassTransferScreen />;
}
