"use client";

import { useState } from "react";
import useSWR from "swr";
import { notFound } from "next/navigation";
import { Activity, Shield, Target, TrendingUp } from "lucide-react";
import { teamsApi } from "@/lib/api/teams";
import { getApiErrorMessage } from "@/lib/api/client";
import { useTeamSearch } from "@/hooks/use-team-search";
import { StatsCard } from "@/components/analytics/stats-card";
import { WinProbabilityChart } from "@/components/analytics/win-probability-chart";
import { TeamIdentity } from "@/components/football/team-identity";
import { HeadToHeadCard } from "@/components/football/head-to-head-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Combobox } from "@/components/ui/combobox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { DetailSkeleton, StatsGridSkeleton } from "@/components/ui/page-skeletons";
import { getResultBg } from "@/lib/utils";

export function TeamDetailView({ teamId }: { teamId: string }) {
  const { data: team, error: teamError, isLoading: teamLoading } = useSWR(
    ["team", teamId],
    () => teamsApi.getById(teamId)
  );
  const { data: stats, isLoading: statsLoading } = useSWR(
    team ? ["team-stats", teamId] : null,
    () => teamsApi.getStats(teamId)
  );
  const { data: trend } = useSWR(team ? ["team-trend", teamId] : null, () =>
    teamsApi.getPerformanceTrend(teamId)
  );

  if (teamLoading) return <DetailSkeleton />;

  if (teamError) {
    const message = getApiErrorMessage(teamError);
    if (message.toLowerCase().includes("not found")) notFound();
    return <ErrorState title="Couldn't load this team" description={message} />;
  }

  if (!team) return null;

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <TeamIdentity name={team.name} fifaCode={team.fifa_code} size="lg" />
        <div className="flex flex-wrap gap-2 sm:ml-auto">
          {team.fifa_ranking != null && <Badge variant="secondary">FIFA #{team.fifa_ranking}</Badge>}
          {team.elo_rating != null && <Badge variant="secondary">Elo {team.elo_rating}</Badge>}
          {team.wc2026_group && <Badge variant="default">Group {team.wc2026_group}</Badge>}
          {team.confederation && <Badge variant="outline">{team.confederation}</Badge>}
        </div>
      </div>

      {statsLoading ? (
        <StatsGridSkeleton count={4} />
      ) : stats ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatsCard title="Win Rate" value={`${(stats.win_rate * 100).toFixed(1)}%`} icon={TrendingUp} color="primary" />
          <StatsCard title="Goals Scored" value={stats.goals_scored} icon={Target} color="accent" />
          <StatsCard title="Clean Sheets" value={stats.clean_sheets} icon={Shield} color="purple" />
          <StatsCard title="Matches Played" value={stats.matches_played} icon={Activity} color="draw" />
        </div>
      ) : null}

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="trend">Performance Trend</TabsTrigger>
          <TabsTrigger value="h2h">Head to Head</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <Card>
            <CardContent className="p-5">
              {stats?.form && stats.form.length > 0 ? (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-fg-muted">Recent form:</span>
                  {stats.form.slice(-5).map((result, i) => (
                    <span
                      key={i}
                      className={`inline-flex h-7 w-7 items-center justify-center rounded-full border text-xs font-bold ${getResultBg(result)}`}
                    >
                      {result}
                    </span>
                  ))}
                </div>
              ) : (
                <EmptyState icon={Activity} title="No recent form data" />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="trend">
          {trend && trend.length > 0 ? (
            <WinProbabilityChart data={trend} teamName={team.name} />
          ) : (
            <Card>
              <CardContent className="p-5">
                <EmptyState icon={TrendingUp} title="No trend data available yet" />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="h2h">
          <HeadToHeadLookup teamId={teamId} teamName={team.name} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function HeadToHeadLookup({ teamId, teamName }: { teamId: string; teamName: string }) {
  const [opponentQuery, setOpponentQuery] = useState("");
  const [opponentId, setOpponentId] = useState<string | undefined>();
  const { results, loading: searching } = useTeamSearch(opponentQuery);

  const { data: h2h, isLoading } = useSWR(
    opponentId ? ["head-to-head", teamId, opponentId] : null,
    () => teamsApi.getHeadToHead(teamId, opponentId!)
  );
  const opponentName = results.find((t) => t.id === opponentId)?.name ?? "Opponent";

  return (
    <Card>
      <CardContent className="space-y-4 p-5">
        <div className="max-w-sm space-y-1.5">
          <label htmlFor="opponent_combobox" className="text-sm font-medium text-foreground">
            Compare against
          </label>
          <Combobox
            id="opponent_combobox"
            aria-label="Search for an opponent team"
            value={opponentId}
            onValueChange={setOpponentId}
            onSearchChange={setOpponentQuery}
            loading={searching}
            placeholder="Search a team…"
            options={results.filter((t) => t.id !== teamId).map((t) => ({ value: t.id, label: t.name, description: t.country }))}
          />
        </div>

        {isLoading && opponentId && <DetailSkeleton />}
        {h2h && (
          <HeadToHeadCard stats={h2h} homeTeam={teamName} awayTeam={opponentName} />
        )}
        {!opponentId && (
          <EmptyState icon={Shield} title="Pick an opponent" description="Search for a team above to see head-to-head history." />
        )}
      </CardContent>
    </Card>
  );
}
