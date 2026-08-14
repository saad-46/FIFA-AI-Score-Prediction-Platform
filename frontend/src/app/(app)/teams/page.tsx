import type { Metadata } from "next";
import { Users } from "lucide-react";
import { TeamsView } from "@/components/teams/teams-view";

export const metadata: Metadata = {
  title: "World Cup 2026 Teams",
  description: "Browse all 48 teams competing at the 2026 FIFA World Cup, with group, FIFA ranking and Elo rating.",
};

export default function TeamsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-foreground font-mono uppercase">
          <Users className="h-6 w-6 text-primary" aria-hidden="true" />
          World Cup 2026 Teams
        </h1>
        <p className="mt-1 text-sm text-fg-muted">
          All 48 teams competing at the 2026 FIFA World Cup.
        </p>
      </div>
      <TeamsView />
    </div>
  );
}
