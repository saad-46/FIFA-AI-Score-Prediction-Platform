"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { Search, Users } from "lucide-react";
import { teamsApi } from "@/lib/api/teams";
import { getApiErrorMessage } from "@/lib/api/client";
import { useTeamSearch } from "@/hooks/use-team-search";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TeamCard } from "@/components/teams/team-card";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { CardGridSkeleton } from "@/components/ui/page-skeletons";

export function TeamsView() {
  const [query, setQuery] = useState("");
  const { results: searchResults, loading: searching } = useTeamSearch(query);
  const {
    data: topTeams,
    error: topError,
    isLoading: topLoading,
    mutate: retryTop,
  } = useSWR("teams-top", () => teamsApi.getTopTeams(20));

  const isSearching = query.trim().length >= 2;

  return (
    <div className="space-y-8">
      <div className="relative w-full sm:w-72">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-fg-muted" aria-hidden="true" />
        <Input
          placeholder="Search teams..."
          className="pl-9"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search teams"
        />
      </div>

      {isSearching ? (
        <Card>
          <CardHeader>
            <CardTitle>Search results</CardTitle>
          </CardHeader>
          <CardContent>
            {searching ? (
              <CardGridSkeleton count={4} />
            ) : searchResults.length === 0 ? (
              <EmptyState icon={Search} title="No teams found" description={`No matches for "${query}".`} />
            ) : (
              <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {searchResults.map((team) => (
                  <li key={team.id}>
                    <Link
                      href={`/teams/${team.id}`}
                      className="flex items-center justify-between rounded-lg border border-border px-4 py-3 text-sm transition-colors hover:border-primary/30 hover:bg-surface-2/50"
                    >
                      <span className="font-medium text-foreground">{team.name}</span>
                      <span className="text-fg-muted">{team.country}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Top Teams by Win Rate</CardTitle>
          </CardHeader>
          <CardContent>
            {topLoading ? (
              <CardGridSkeleton count={6} />
            ) : topError ? (
              <ErrorState
                title="Couldn't load the leaderboard"
                description={getApiErrorMessage(topError)}
                onRetry={() => retryTop()}
              />
            ) : !topTeams || topTeams.length === 0 ? (
              <EmptyState icon={Users} title="No team stats available yet" />
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {topTeams.map((stats, i) => (
                  <TeamCard key={stats.team_id} stats={stats} rank={i + 1} delay={i * 0.03} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
