import type { Metadata } from "next";
import { Users } from "lucide-react";
import { TeamsView } from "@/components/teams/teams-view";

export const metadata: Metadata = {
  title: "Candidacy Registry",
  description: "Browse team credentials, dynamic Elo ratings, and tournament seeding parameters.",
};

export default function TeamsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-foreground font-mono uppercase">
          <Users className="h-6 w-6 text-primary" aria-hidden="true" />
          Candidacy Registry
        </h1>
        <p className="mt-1 text-sm text-fg-muted">Performance profiles and validation statistics for FIFA World Cup contestants</p>
      </div>
      <TeamsView />
    </div>
  );
}
