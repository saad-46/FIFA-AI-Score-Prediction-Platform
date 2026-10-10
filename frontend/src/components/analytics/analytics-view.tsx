"use client";

import useSWR from "swr";
import { BarChart3, Target, TrendingUp } from "lucide-react";
import { analyticsApi } from "@/lib/api/analytics";
import { matchesApi } from "@/lib/api/matches";
import { getApiErrorMessage } from "@/lib/api/client";
import { StatsCard, StatsRow } from "@/components/analytics/stats-card";
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
        <StatsRow>
          <StatsCard title="Matches" value={global.total_matches.toLocaleString()} subtitle={`${global.total_goals.toLocaleString()} goals`} />
          <StatsCard title="Goals per match" value={global.avg_goals_per_match.toFixed(2)} subtitle="Both teams combined" />
          <StatsCard title="First-listed team wins" value={`${(global.home_win_rate * 100).toFixed(1)}%`} subtitle="The side listed as home" />
          <StatsCard title="Draws" value={`${(global.draw_rate * 100).toFixed(1)}%`} subtitle="Level after the recorded score" />
        </StatsRow>
      )}
      {/* This line used to claim the opposite — "the full historical dataset
          across all competitions, not only World Cup matches". That was stale:
          /analytics/global reads load_matches_dataframe(), which is explicitly
          filtered to the WC-only corpus so live inference matches training (see
          ml/data/loader.py). The endpoint's own top_tournaments confirms it —
          seven entries, all FIFA World Cups. Browsing the wider ~49k-row table
          is what /matches does; these figures are not that. */}
      <p className="-mt-4 max-w-3xl text-xs leading-relaxed text-fg-subtle">
        Figures cover World Cup matches only ({global?.total_matches.toLocaleString() ?? "—"} matches,
        2002–2026) — the same corpus the model is trained and served on. The full historical record is
        browsable under Matches.
      </p>

      <Tabs defaultValue="overview">
        <TabsList aria-label="Analytics sections">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="goals">Goal timing</TabsTrigger>
          <TabsTrigger value="results">Scorelines</TabsTrigger>
          <TabsTrigger value="model">Model accuracy</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Goals per match, by year</CardTitle>
              </CardHeader>
              <CardContent>
                {/* Real aggregates from the same response as the tiles above.
                    Bars start at zero; the figure beside each is the value. */}
                {global && global.goals_by_year.length > 0 ? (
                  <ul className="space-y-2" aria-label="Average goals per match for each year in the dataset">
                    {(() => {
                      const rows = global.goals_by_year
                        .filter((y) => y.matches > 0)
                        .map((y) => ({ ...y, avg: y.goals / y.matches }));
                      const max = Math.max(...rows.map((r) => r.avg), 0.01);
                      return rows.map((r) => (
                        <li key={r.year} className="grid grid-cols-[3rem_1fr_6.5rem] items-center gap-3 text-sm">
                          <span className="tabular font-semibold text-foreground">{r.year}</span>
                          <span className="h-2 overflow-hidden rounded-full bg-surface-3" aria-hidden="true">
                            <span className="block h-full rounded-full bg-primary" style={{ width: `${(r.avg / max) * 100}%` }} />
                          </span>
                          <span className="tabular text-right text-fg-muted">
                            <span className="font-semibold text-foreground">{r.avg.toFixed(2)}</span>
                            <span className="ml-1.5 text-xs text-fg-subtle">{r.matches} m</span>
                          </span>
                        </li>
                      ));
                    })()}
                  </ul>
                ) : (
                  <p className="text-sm text-fg-muted">No yearly breakdown is available.</p>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>How matches ended</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {global && (
                  <>
                    <ProbabilityBar label="First-listed team won" value={global.home_win_rate} tone="primary" />
                    <ProbabilityBar label="Draw" value={global.draw_rate} tone="draw" />
                    <ProbabilityBar label="Second-listed team won" value={global.away_win_rate} tone="primary" />
                    <p className="pt-1 text-xs leading-relaxed text-fg-subtle">
                      Most World Cup matches are on neutral ground, so &ldquo;home&rdquo; here means the team
                      listed first, not a team playing in its own country.
                    </p>
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
            <EmptyState icon={Target} title="No goal-timing data is available" />
          )}
        </TabsContent>

        <TabsContent value="results">
          {scorelinesLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : scorelines && scorelines.length > 0 ? (
            <ScorelineFrequencyChart data={scorelines} />
          ) : (
            <EmptyState icon={BarChart3} title="No scoreline data is available" />
          )}
        </TabsContent>

        <TabsContent value="model">
          {evaluationLoading ? (
            <StatsGridSkeleton count={3} />
          ) : evaluation ? (
            <div className="space-y-5">
              <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-3">
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
              </dl>

              <p className="text-sm text-fg-muted">{evaluation.evaluation_description}</p>

              {/* The legacy figure is kept visible but explicitly dated and
                  labelled. Silently dropping it would hide that the number
                  users saw yesterday came from a different model entirely. */}
              {evaluation.legacy && (
                <details className="rounded-lg border border-border bg-surface px-4 py-3">
                  <summary className="cursor-pointer rounded text-sm font-semibold text-fg-muted hover:text-foreground">
                    {evaluation.legacy.label ?? "Legacy model metrics"}
                  </summary>
                  <div className="pt-3 space-y-1.5 text-xs text-fg-muted">
                    <p>{evaluation.legacy.note}</p>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 pt-1 text-xs sm:grid-cols-4">
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
      <dt className="text-fg-subtle">{label}</dt>
      <dd className="tabular font-semibold text-foreground">{value}</dd>
    </div>
  );
}

function ModelStat({ label, value, desc }: { label: string; value: string; desc: string }) {
  return (
    <div className="bg-surface px-5 py-4">
      <dt className="eyebrow">{label}</dt>
      <dd className="scoreline mt-2 break-words text-3xl text-foreground">{value}</dd>
      <dd className="mt-1.5 text-xs text-fg-subtle">{desc}</dd>
    </div>
  );
}
