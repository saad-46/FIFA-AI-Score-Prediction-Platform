import type { Metadata } from "next";
import { Activity } from "lucide-react";
import { MatchesView } from "@/components/matches/matches-view";

export const metadata: Metadata = {
  title: "Historical Registry",
  description: "Browse historical FIFA match results and performance records.",
};

export default function MatchesPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-foreground font-mono uppercase">
          <Activity className="h-6 w-6 text-primary" aria-hidden="true" />
          Historical Registry
        </h1>
        <p className="mt-1 text-sm text-fg-muted">Archive of historical matches, scorelines, and tournament results</p>
      </div>
      <MatchesView />
    </div>
  );
}
