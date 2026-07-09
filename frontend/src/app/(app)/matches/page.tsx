import type { Metadata } from "next";
import { Activity } from "lucide-react";
import { MatchesView } from "@/components/matches/matches-view";

export const metadata: Metadata = {
  title: "Match History",
  description: "Browse historical FIFA match results and filter by team or tournament.",
};

export default function MatchesPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
          <Activity className="h-6 w-6 text-primary" aria-hidden="true" />
          Match History
        </h1>
        <p className="mt-1 text-sm text-fg-muted">Browse historical FIFA match results</p>
      </div>
      <MatchesView />
    </div>
  );
}
