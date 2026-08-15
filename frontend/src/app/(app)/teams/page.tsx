import type { Metadata } from "next";
import { Users } from "lucide-react";
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
        icon={Users}
        title="World Cup 2026 Teams"
        description="All 48 teams competing at the 2026 FIFA World Cup."
      />
      <TeamsView />
    </div>
  );
}
