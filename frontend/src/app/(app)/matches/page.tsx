import type { Metadata } from "next";
import { MatchesView } from "@/components/matches/matches-view";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = {
  title: "Matches",
  description: "Browse match results from the record, by team and competition.",
};

export default function MatchesPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Matches"
        description="Results from the match record, newest first. Filter by team or competition."
      />
      <MatchesView />
    </div>
  );
}
