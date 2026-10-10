import type { Metadata } from "next";
import { TeamsView } from "@/components/teams/teams-view";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = {
  title: "World Cup 2026 Teams",
  description: "Browse all 48 teams competing at the 2026 FIFA World Cup, with group, FIFA ranking and Elo rating.",
};

export default function TeamsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="FIFA World Cup 2026"
        title="Teams"
        description="All 48 qualifiers. Sort by group, FIFA ranking or Elo rating, and open a team for its captain, key players and full squad."
      />
      <TeamsView />
    </div>
  );
}
