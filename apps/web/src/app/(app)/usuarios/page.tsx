import type { Metadata } from "next";
import { UsersScreen } from "@/features/users/users-screen";

export const metadata: Metadata = { title: "Usuarios · Reclutamiento IA" };

export default function UsersPage() {
  return <UsersScreen />;
}
