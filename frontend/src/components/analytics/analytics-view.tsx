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
  const { data: metrics, isLoading: metricsLoading } = useSWR("model-metrics", analyticsApi.getModelMetrics);
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
          <StatsCard title="Home Win Rate" value={`${(global.home_win_rate * 100).toFixed(1)}%`} icon={TrendingUp} color="purple" delay={0.1} />
          <StatsCard title="Draw Rate" value={`${(global.draw_rate * 100).toFixed(1)}%`} icon={BarChart3} color="draw" delay={0.15} />
        </div>
      )}
      <p className="-mt-4 text-xs text-fg-muted">
        Figures reflect the full historical dataset across all competitions, not only World Cup matches.
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
          {metricsLoading ? (
            <StatsGridSkeleton count={3} />
          ) : metrics ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <ModelStat label="Model Accuracy" value={`${(metrics.accuracy * 100).toFixed(1)}%`} desc="Correct result predictions" />
              <ModelStat label="Mean Abs Error" value={metrics.mae.toFixed(2)} desc="Average goal prediction error" />
              <ModelStat label="Training Samples" value={metrics.training_samples.toLocaleString()} desc="Matches used for training" />
            </div>
          ) : (
            <EmptyState icon={TrendingUp} title="Model metrics unavailable" />
          )}
        </TabsContent>
      </Tabs>
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
