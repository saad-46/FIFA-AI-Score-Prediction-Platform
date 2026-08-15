import type { Metadata } from "next";
import { Activity } from "lucide-react";
import { MatchesView } from "@/components/matches/matches-view";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = {
  title: "Historical Registry",
  description: "Browse historical FIFA match results and performance records.",
};

export default function MatchesPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        icon={Activity}
        title="Historical Registry"
        description="Archive of historical matches, scorelines, and tournament results"
      />
      <MatchesView />
    </div>
  );
}
