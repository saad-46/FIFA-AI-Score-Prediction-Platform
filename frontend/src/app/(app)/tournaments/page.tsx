import type { Metadata } from "next";
import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { TournamentTabs } from "@/components/tournament/tournament-tabs";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = {
  title: "World Cup 2026",
  description: "FIFA World Cup 2026: the full bracket, group tables, schedule, tournament simulator and model evaluation.",
};

export default function TournamentsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="11 June – 19 July 2026 · Canada, Mexico, USA"
        title="World Cup 2026"
        description="The completed tournament: every knockout tie, the final group tables and the schedule, plus a simulator and a match-by-match check of the model's predictions."
      />
      {/* useSearchParams needs a Suspense boundary to keep the page statically renderable. */}
      <Suspense fallback={<Skeleton className="h-96 w-full rounded-lg" />}>
        <TournamentTabs />
      </Suspense>
    </div>
  );
}
