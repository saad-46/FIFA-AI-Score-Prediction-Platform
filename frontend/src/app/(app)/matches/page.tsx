import type { Metadata } from "next";
import { Activity } from "lucide-react";
import { MatchesView } from "@/components/matches/matches-view";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = {
  title: "World Cup Matches",
  description: "Browse World Cup match results and scorelines from the historical record.",
};

export default function MatchesPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        icon={Activity}
        title="World Cup Matches"
        description="Results and scorelines from the historical match record"
      />
      <MatchesView />
    </div>
  );
}
