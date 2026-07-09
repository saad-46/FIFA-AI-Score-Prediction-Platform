import type { Metadata } from "next";
import { Users } from "lucide-react";
import { TeamsView } from "@/components/teams/teams-view";

export const metadata: Metadata = {
  title: "Teams",
  description: "Browse FIFA World Cup 2026 teams, rankings, and Elo ratings.",
};

export default function TeamsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
          <Users className="h-6 w-6 text-primary" aria-hidden="true" />
          Teams
        </h1>
        <p className="mt-1 text-sm text-fg-muted">Browse and compare team statistics</p>
      </div>
      <TeamsView />
    </div>
  );
}
