"use client";

import useSWR from "swr";
import Link from "next/link";
import { Brain, BarChart3, Users, Activity, TrendingUp, Trophy } from "lucide-react";
import { analyticsApi } from "@/lib/api/analytics";
import { getApiErrorMessage } from "@/lib/api/client";
import { StatsCard } from "@/components/analytics/stats-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { StatsGridSkeleton } from "@/components/ui/page-skeletons";
import { formatPercent } from "@/lib/utils";
import { getCountryFlag } from "@/components/football/team-identity";

const QUICK_ACTIONS = [
  { href: "/predict", icon: Brain, title: "Simulation Engine", description: "Configure and run high-fidelity match simulations" },
  { href: "/analytics", icon: BarChart3, title: "Insights", description: "Explore historical match data and performance trends" },
  { href: "/tournaments", icon: Trophy, title: "Tournament Intelligence", description: "Groups, schedules, and Monte Carlo probability flows" },
] as const;

export function DashboardView() {
  const { data: stats, error, isLoading, mutate } = useSWR("dashboard-stats", analyticsApi.getDashboardStats);

  return (
    <div className="space-y-8">
      {isLoading ? (
        <StatsGridSkeleton count={4} />
      ) : error ? (
        <ErrorState title="Couldn't load your dashboard" description={getApiErrorMessage(error)} onRetry={() => mutate()} />
      ) : stats ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatsCard title="Total Projections" value={stats.total_predictions.toLocaleString()} icon={Brain} color="primary" delay={0} />
          <StatsCard title="Accuracy Rate" value={formatPercent(stats.accuracy_rate)} icon={TrendingUp} color="accent" delay={0.05} />
          <StatsCard title="Matches Analyzed" value={stats.total_matches_analyzed.toLocaleString()} icon={Activity} color="purple" delay={0.1} />
          <StatsCard title="Teams Tracked" value={stats.total_teams.toLocaleString()} icon={Users} color="draw" delay={0.15} />
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {QUICK_ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <Link key={action.href} href={action.href} className="focus-visible:outline-none">
              <Card interactive className="overflow-hidden border-border/40 bg-surface/30 hover:border-primary/40 shadow-md">
                <CardContent className="p-5">
                  <div className="mb-3 inline-flex rounded border border-primary/25 bg-primary/10 p-2.5">
                    <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
                  </div>
                  <h3 className="font-semibold text-foreground tracking-tight">{action.title}</h3>
                  <p className="mt-1 text-sm text-fg-muted leading-relaxed">{action.description}</p>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>

      <Card className="border-border/40">
        <CardHeader className="pb-2 border-b border-border/20">
          <CardTitle className="font-mono text-xs tracking-wider uppercase text-foreground">Recent Prediction Reports</CardTitle>
        </CardHeader>
        <CardContent>
          {stats?.recent_predictions && stats.recent_predictions.length > 0 ? (
            <ul className="space-y-1 pt-2">
              {stats.recent_predictions.map((p) => (
                <li key={p.id} className="flex items-center justify-between text-sm py-2.5 border-b border-border/20 last:border-0">
                  <span className="text-foreground flex items-center gap-2">
                    <span className="text-base select-none">{getCountryFlag(p.home_team)}</span>
                    <span className="font-medium text-xs tracking-tight">{p.home_team}</span>
                    <span className="text-zinc-600 font-mono text-[9px] mx-1">VS</span>
                    <span className="text-base select-none">{getCountryFlag(p.away_team)}</span>
                    <span className="font-medium text-xs tracking-tight">{p.away_team}</span>
                  </span>
                  <span className="font-mono text-xs font-bold text-cyan-400 bg-surface-2/65 px-2 py-0.5 rounded border border-border/40 shadow-sm">
                    {p.predicted_home_score} – {p.predicted_away_score}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              icon={Brain}
              title="No predictions yet"
              description="Make your first prediction to see it here."
              action={
                <Button asChild>
                  <Link href="/predict">Make a prediction</Link>
                </Button>
              }
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
