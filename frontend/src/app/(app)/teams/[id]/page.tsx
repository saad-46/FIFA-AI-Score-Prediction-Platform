import type { Metadata } from "next";
import { TeamDetailView } from "@/components/teams/team-detail-view";

interface TeamPageProps {
  params: Promise<{ id: string }>;
}

export const metadata: Metadata = { title: "Team Details" };

export default async function TeamPage({ params }: TeamPageProps) {
  const { id } = await params;
  return <TeamDetailView teamId={id} />;
}
