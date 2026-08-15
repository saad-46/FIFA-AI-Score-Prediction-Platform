import type { Metadata } from "next";
import { Trophy } from "lucide-react";
import { TournamentTabs } from "@/components/tournament/tournament-tabs";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = {
  title: "Tournament Intelligence",
  description: "Official FIFA World Cup 2026 groups, schedule, and AI-simulated tournament outlook.",
};

export default function TournamentsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        icon={Trophy}
        title="Tournament Intelligence"
        description="FIFA World Cup 2026 groups, match schedules, and Monte Carlo bracket outcomes"
      />
      <TournamentTabs />
    </div>
  );
}
