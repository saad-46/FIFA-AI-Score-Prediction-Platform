import type { Metadata } from "next";
import { Trophy } from "lucide-react";
import { TournamentTabs } from "@/components/tournament/tournament-tabs";

export const metadata: Metadata = {
  title: "Tournament Intelligence",
  description: "Official FIFA World Cup 2026 groups, schedule, and AI-simulated tournament outlook.",
};

export default function TournamentsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-foreground font-mono uppercase">
          <Trophy className="h-6 w-6 text-primary" aria-hidden="true" />
          Tournament Intelligence
        </h1>
        <p className="mt-1 text-sm text-fg-muted">
          FIFA World Cup 2026 groups, match schedules, and Monte Carlo bracket outcomes
        </p>
      </div>
      <TournamentTabs />
    </div>
  );
}
