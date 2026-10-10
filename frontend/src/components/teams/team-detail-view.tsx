"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Shield, Swords, TrendingUp } from "lucide-react";
import { TeamSquadSection } from "@/components/teams/team-squad-section";
import { teamsApi } from "@/lib/api/teams";
import { getApiErrorMessage } from "@/lib/api/client";
import { useTeamSearch } from "@/hooks/use-team-search";
import { StatsCard, StatsRow } from "@/components/analytics/stats-card";
import { WinProbabilityChart } from "@/components/analytics/win-probability-chart";
import { TeamFlag } from "@/components/football/team-flag";
import { HeadToHeadCard } from "@/components/football/head-to-head-card";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeader } from "@/components/ui/section";
import { DetailSkeleton, StatsGridSkeleton } from "@/components/ui/page-skeletons";
import { cn } from "@/lib/utils";

const RESULT_WORD = { W: "Win", D: "Draw", L: "Loss" } as const;

/** One result in a form guide. The letter carries the meaning; colour supports it. */
function FormPip({ result }: { result: "W" | "D" | "L" }) {
  return (
    <li
      className={cn(
        "flex h-7 w-7 items-center justify-center rounded text-xs font-bold",
        result === "W" && "bg-win/15 text-win",
        result === "D" && "bg-surface-3 text-fg-muted",
        result === "L" && "bg-loss/15 text-loss"
      )}
    >
      <span aria-hidden="true">{result}</span>
      <span className="sr-only">{RESULT_WORD[result]}</span>
    </li>
  );
}

/**
 * A national team's profile.
 *
 * Order follows what a reader comes for: who they are, who plays for them,
 * then how they have done. The match-record tiles used to sit directly under
 * the header, ahead of the squad, so every profile opened on four numbers
 * before showing a single player.
 */
export function TeamDetailView({ teamId }: { teamId: string }) {
  const { data: team, error: teamError, isLoading: teamLoading, mutate: retryTeam } = useSWR(["team", teamId], () =>
    teamsApi.getById(teamId)
  );
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
    mutate: retryStats,
  } = useSWR(team ? ["team-stats", teamId] : null, () => teamsApi.getStats(teamId));
  const { data: trend } = useSWR(team ? ["team-trend", teamId] : null, () => teamsApi.getPerformanceTrend(teamId));

  if (teamLoading) return <DetailSkeleton />;

  if (teamError) {
    const message = getApiErrorMessage(teamError);
    if (message.toLowerCase().includes("not found")) notFound();
    return <ErrorState title="Couldn't load this team" description={message} onRetry={() => retryTeam()} />;
  }

  if (!team) return null;

  const facts = [
    team.wc2026_group ? { label: "Group", value: team.wc2026_group } : null,
    team.fifa_ranking != null ? { label: "FIFA rank", value: `#${team.fifa_ranking}` } : null,
    team.elo_rating != null ? { label: "Elo", value: String(team.elo_rating) } : null,
  ].filter((f): f is { label: string; value: string } => f !== null);

  const form = (stats?.form ?? []).slice(-5) as ("W" | "D" | "L")[];

  return (
    <div className="space-y-10">
      <nav aria-label="Breadcrumb">
        <Link
          href="/teams"
          className="inline-flex min-h-9 items-center gap-1.5 rounded text-sm text-fg-muted transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          All teams
        </Link>
      </nav>

      {/* ── Identity ─────────────────────────────────────────────────────── */}
      <header className="flex flex-col gap-6 border-b border-border pb-8 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex min-w-0 items-center gap-4 sm:gap-5">
          <TeamFlag name={team.name} fifaCode={team.fifa_code} size="xl" className="shrink-0" />
          <div className="min-w-0">
            <p className="eyebrow">
              {[team.fifa_code, team.confederation].filter(Boolean).join(" · ") || "National team"}
            </p>
            <h1 className="mt-1 break-normal font-display text-4xl font-bold uppercase leading-none tracking-wide text-foreground sm:text-6xl">
              {team.name}
            </h1>
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
          {facts.length > 0 && (
            <dl className="flex gap-8">
              {facts.map((f) => (
                <div key={f.label}>
                  <dt className="eyebrow">{f.label}</dt>
                  <dd className="scoreline mt-1 text-3xl text-foreground">{f.value}</dd>
                </div>
              ))}
            </dl>
          )}
          <Button asChild variant="outline">
            <Link href="/predict">
              <Swords aria-hidden="true" />
              Predict a match
            </Link>
          </Button>
        </div>
      </header>

      {/* ── Squad ────────────────────────────────────────────────────────── */}
      <TeamSquadSection teamId={teamId} />

      {/* ── Record ───────────────────────────────────────────────────────── */}
      <section aria-labelledby="record-heading" className="space-y-5">
        <SectionHeader
          id="record-heading"
          title="Match record"
          meta={stats ? `${stats.matches_played.toLocaleString()} matches on record` : undefined}
        />

        {statsLoading ? (
          <StatsGridSkeleton count={4} />
        ) : statsError ? (
          <ErrorState
            title="Couldn't load the match record"
            description={getApiErrorMessage(statsError)}
            onRetry={() => retryStats()}
          />
        ) : stats ? (
          <>
            <StatsRow>
              <StatsCard title="Win rate" value={`${(stats.win_rate * 100).toFixed(1)}%`} subtitle={`${stats.wins} W · ${stats.draws} D · ${stats.losses} L`} />
              <StatsCard title="Goals for" value={stats.goals_scored} subtitle={`${stats.avg_goals_scored.toFixed(2)} per match`} />
              <StatsCard title="Goals against" value={stats.goals_conceded} subtitle={`${stats.avg_goals_conceded.toFixed(2)} per match`} />
              <StatsCard title="Clean sheets" value={stats.clean_sheets} subtitle={`of ${stats.matches_played} matches`} />
            </StatsRow>

            {form.length > 0 && (
              <div className="flex items-center gap-3">
                <p id="form-label" className="eyebrow">
                  Last {form.length}
                </p>
                <ol aria-labelledby="form-label" className="flex gap-1.5">
                  {form.map((r, i) => (
                    <FormPip key={i} result={r} />
                  ))}
                </ol>
                <p className="text-xs text-fg-subtle">Oldest first</p>
              </div>
            )}
          </>
        ) : null}

        <Tabs defaultValue="trend">
          <TabsList aria-label="Match record views">
            <TabsTrigger value="trend">Results over time</TabsTrigger>
            <TabsTrigger value="h2h">Head to head</TabsTrigger>
          </TabsList>

          <TabsContent value="trend">
            {trend && trend.length > 0 ? (
              <WinProbabilityChart data={trend} teamName={team.name} />
            ) : (
              <EmptyState icon={TrendingUp} title="No results in this period" description="There are no matches on record for the last 24 months." />
            )}
          </TabsContent>

          <TabsContent value="h2h">
            <HeadToHeadLookup teamId={teamId} teamName={team.name} />
          </TabsContent>
        </Tabs>
      </section>
    </div>
  );
}

function HeadToHeadLookup({ teamId, teamName }: { teamId: string; teamName: string }) {
  const [opponentQuery, setOpponentQuery] = useState("");
  const [opponentId, setOpponentId] = useState<string | undefined>();
  const { results, loading: searching } = useTeamSearch(opponentQuery);

  const { data: h2h, isLoading, error } = useSWR(opponentId ? ["head-to-head", teamId, opponentId] : null, () =>
    teamsApi.getHeadToHead(teamId, opponentId!)
  );
  const opponentName = results.find((t) => t.id === opponentId)?.name ?? "Opponent";

  return (
    <div className="space-y-4">
      <div className="max-w-sm space-y-1.5">
        <label htmlFor="opponent_combobox" className="eyebrow block">
          Opponent
        </label>
        <Combobox
          id="opponent_combobox"
          aria-label="Search for an opponent team"
          value={opponentId}
          onValueChange={setOpponentId}
          onSearchChange={setOpponentQuery}
          loading={searching}
          placeholder="Search for a team…"
          searchPlaceholder="Type at least two letters…"
          emptyMessage={opponentQuery.trim().length < 2 ? "Type at least two letters." : "No team matches that."}
          options={results.filter((t) => t.id !== teamId).map((t) => ({ value: t.id, label: t.name, description: t.country }))}
        />
      </div>

      {isLoading && opponentId && <DetailSkeleton />}
      {error && <ErrorState title="Couldn't load the head-to-head record" description={getApiErrorMessage(error)} />}
      {h2h && <HeadToHeadCard stats={h2h} homeTeam={teamName} awayTeam={opponentName} />}
      {!opponentId && (
        <EmptyState icon={Shield} title="Pick an opponent" description={`Search for a team to see its record against ${teamName}.`} />
      )}
    </div>
  );
}
