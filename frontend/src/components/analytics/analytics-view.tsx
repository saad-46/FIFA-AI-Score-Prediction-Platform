"use client";

import useSWR from "swr";
import { Activity, BarChart3, Target, TrendingUp } from "lucide-react";
import { analyticsApi } from "@/lib/api/analytics";
import { matchesApi } from "@/lib/api/matches";
import { getApiErrorMessage } from "@/lib/api/client";
import { StatsCard } from "@/components/analytics/stats-card";
import { GoalDistributionChart } from "@/components/analytics/goal-distribution-chart";
import { ScorelineFrequencyChart } from "@/components/analytics/scoreline-frequency-chart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ProbabilityBar } from "@/components/ui/probability-bar";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { StatsGridSkeleton } from "@/components/ui/page-skeletons";
import { Skeleton } from "@/components/ui/skeleton";

export function AnalyticsView() {
  const { data: global, error: globalError, isLoading: globalLoading, mutate: retryGlobal } = useSWR(
    "analytics-global",
    analyticsApi.getGlobalAnalytics
  );
  // The honest headline: the frozen V2 model's out-of-sample WC2026 backtest,
  // not the legacy v1 training metrics that /model-metrics returns.
  const { data: evaluation, isLoading: evaluationLoading } = useSWR(
    "model-evaluation",
    analyticsApi.getModelEvaluation,
    { revalidateOnFocus: false }
  );
  const { data: goalDist, isLoading: goalDistLoading } = useSWR("goal-distribution", () =>
    matchesApi.getGoalDistribution()
  );
  const { data: scorelines, isLoading: scorelinesLoading } = useSWR("scoreline-frequency", () =>
    matchesApi.getScorelineFrequency()
  );

  if (globalLoading) return <StatsGridSkeleton count={4} />;

  if (globalError) {
    return (
      <ErrorState
        title="Couldn't load analytics"
        description={getApiErrorMessage(globalError)}
        onRetry={() => retryGlobal()}
      />
    );
  }

  return (
    <div className="space-y-8">
      {global && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatsCard title="Total Matches" value={global.total_matches.toLocaleString()} icon={Activity} color="primary" delay={0} />
          <StatsCard title="Avg Goals/Match" value={global.avg_goals_per_match.toFixed(2)} icon={Target} color="accent" delay={0.05} />
          <StatsCard title="Home Win Rate" value={`${(global.home_win_rate * 100).toFixed(1)}%`} icon={TrendingUp} color="accent" delay={0.1} />
          <StatsCard title="Draw Rate" value={`${(global.draw_rate * 100).toFixed(1)}%`} icon={BarChart3} color="draw" delay={0.15} />
        </div>
      )}
      {/* This line used to claim the opposite — "the full historical dataset
          across all competitions, not only World Cup matches". That was stale:
          /analytics/global reads load_matches_dataframe(), which is explicitly
          filtered to the WC-only corpus so live inference matches training (see
          ml/data/loader.py). The endpoint's own top_tournaments confirms it —
          seven entries, all FIFA World Cups. Browsing the wider ~49k-row table
          is what /matches does; these figures are not that. */}
      <p className="-mt-4 text-xs text-fg-muted">
        Figures cover World Cup matches only ({global?.total_matches.toLocaleString() ?? "—"} matches,
        2002–2026) — the same corpus the model is trained and served on. The full historical record is
        browsable under Matches.
      </p>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="goals">Goals</TabsTrigger>
          <TabsTrigger value="results">Results</TabsTrigger>
          <TabsTrigger value="model">Model</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Top Tournaments</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {global?.top_tournaments.slice(0, 6).map((t) => (
                  <div key={t.tournament} className="flex justify-between text-sm">
                    <span className="text-foreground">{t.tournament}</span>
                    <span className="font-mono text-fg-muted">{t.matches.toLocaleString()}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Result Distribution</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {global && (
                  <>
                    <ProbabilityBar label="Home Win" value={global.home_win_rate} tone="win" />
                    <ProbabilityBar label="Draw" value={global.draw_rate} tone="draw" />
                    <ProbabilityBar label="Away Win" value={global.away_win_rate} tone="loss" />
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="goals">
          {goalDistLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : goalDist && goalDist.length > 0 ? (
            <GoalDistributionChart data={goalDist} />
          ) : (
            <EmptyState icon={Target} title="No goal distribution data available" />
          )}
        </TabsContent>

        <TabsContent value="results">
          {scorelinesLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : scorelines && scorelines.length > 0 ? (
            <ScorelineFrequencyChart data={scorelines} />
          ) : (
            <EmptyState icon={BarChart3} title="No scoreline data available" />
          )}
        </TabsContent>

        <TabsContent value="model">
          {evaluationLoading ? (
            <StatsGridSkeleton count={3} />
          ) : evaluation ? (
            <div className="space-y-5">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <ModelStat
                  label={`${evaluation.evaluation_name} Accuracy`}
                  value={
                    evaluation.accuracy != null
                      ? `${(evaluation.accuracy * 100).toFixed(1)}%`
                      : "N/A"
                  }
                  desc={
                    evaluation.correct != null && evaluation.total != null
                      ? `${evaluation.correct} of ${evaluation.total} match results correct`
                      : "Out-of-sample evaluation"
                  }
                />
                <ModelStat
                  label="Matches Evaluated"
                  value={evaluation.total != null ? evaluation.total.toLocaleString() : "N/A"}
                  desc="Every WC2026 fixture, none excluded"
                />
                <ModelStat
                  label="Model Version"
                  value={evaluation.model_version.replace(/^v/, "v")}
                  desc="Frozen before the tournament"
                />
              </div>

              <p className="text-sm text-fg-muted">{evaluation.evaluation_description}</p>

              {/* The legacy figure is kept visible but explicitly dated and
                  labelled. Silently dropping it would hide that the number
                  users saw yesterday came from a different model entirely. */}
              {evaluation.legacy && (
                <details className="rounded-lg border border-border bg-surface-2/40 px-4 py-3">
                  <summary className="cursor-pointer font-mono text-[11px] uppercase tracking-wider text-fg-muted">
                    {evaluation.legacy.label ?? "Legacy model metrics"}
                  </summary>
                  <div className="pt-3 space-y-1.5 text-xs text-fg-muted">
                    <p>{evaluation.legacy.note}</p>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 pt-1 font-mono text-[11px] sm:grid-cols-4">
                      <LegacyStat
                        label="Raw accuracy"
                        value={pct(evaluation.legacy.classifier_raw_accuracy)}
                      />
                      <LegacyStat
                        label="Draw-boosted"
                        value={pct(evaluation.legacy.classifier_adjusted_accuracy)}
                      />
                      <LegacyStat
                        label="Training samples"
                        value={evaluation.legacy.training_samples?.toLocaleString() ?? "N/A"}
                      />
                      <LegacyStat
                        label="Version"
                        value={evaluation.legacy.model_version ?? "N/A"}
                      />
                    </dl>
                  </div>
                </details>
              )}
            </div>
          ) : (
            <EmptyState icon={TrendingUp} title="Model evaluation unavailable" />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

/** Formats a 0–1 metric as a percentage, or "N/A" when genuinely absent —
 * never a fabricated zero. */
function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  return `${(value * 100).toFixed(1)}%`;
}

function LegacyStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-fg-muted">{label}</dt>
      <dd className="text-foreground/80 tabular-nums">{value}</dd>
    </div>
  );
}

function ModelStat({ label, value, desc }: { label: string; value: string; desc: string }) {
  return (
    <Card>
      <CardContent className="p-5 text-center">
        <p className="font-mono text-3xl font-black text-primary">{value}</p>
        <p className="mt-1 font-medium text-foreground">{label}</p>
        <p className="mt-0.5 text-xs text-fg-muted">{desc}</p>
      </CardContent>
    </Card>
  );
}
