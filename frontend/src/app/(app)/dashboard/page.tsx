import type { Metadata } from "next";
import { Suspense } from "react";
import {
  Brain,
  BarChart3,
  Users,
  Activity,
  TrendingUp,
  Trophy,
} from "lucide-react";
import { StatsCard } from "@/components/analytics/stats-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export const metadata: Metadata = { title: "Dashboard" };

// In production this would fetch from the API server-side
async function getDashboardData() {
  // Placeholder — replace with real API call using server-side fetch
  return {
    total_predictions: 0,
    accuracy_rate: 0,
    total_matches_analyzed: 44341,
    total_teams: 312,
  };
}

export default async function DashboardPage() {
  const stats = await getDashboardData();

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-slate-400 text-sm mt-1">
            Your AI prediction overview
          </p>
        </div>
        <Button variant="gradient" asChild>
          <Link href="/predict">
            <Brain className="h-4 w-4" />
            New Prediction
          </Link>
        </Button>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Predictions"
          value={stats.total_predictions.toLocaleString()}
          icon={Brain}
          color="emerald"
          delay={0}
        />
        <StatsCard
          title="Accuracy Rate"
          value={`${(stats.accuracy_rate * 100).toFixed(1)}%`}
          icon={TrendingUp}
          color="cyan"
          delay={0.05}
        />
        <StatsCard
          title="Matches Analyzed"
          value={stats.total_matches_analyzed.toLocaleString()}
          icon={Activity}
          color="purple"
          delay={0.1}
        />
        <StatsCard
          title="Teams Tracked"
          value={stats.total_teams.toLocaleString()}
          icon={Users}
          color="amber"
          delay={0.15}
        />
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            href: "/predict",
            icon: Brain,
            title: "AI Prediction",
            description: "Predict the outcome of any match",
            color: "from-emerald-600 to-cyan-600",
          },
          {
            href: "/analytics",
            icon: BarChart3,
            title: "Analytics",
            description: "Explore historical match data",
            color: "from-purple-600 to-blue-600",
          },
          {
            href: "/tournaments",
            icon: Trophy,
            title: "Tournaments",
            description: "World Cup, Euros, and more",
            color: "from-amber-600 to-orange-600",
          },
        ].map((action) => {
          const Icon = action.icon;
          return (
            <Link key={action.href} href={action.href}>
              <Card className="hover:border-slate-600 transition-all duration-200 cursor-pointer group overflow-hidden">
                <CardContent className="p-5">
                  <div
                    className={`inline-flex rounded-lg bg-gradient-to-br ${action.color} p-2.5 mb-3`}
                  >
                    <Icon className="h-5 w-5 text-white" />
                  </div>
                  <h3 className="font-semibold text-slate-200 group-hover:text-white transition-colors">
                    {action.title}
                  </h3>
                  <p className="text-sm text-slate-500 mt-1">
                    {action.description}
                  </p>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>

      {/* Recent activity placeholder */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Predictions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Brain className="h-12 w-12 text-slate-700 mb-4" />
            <p className="text-slate-400 font-medium">No predictions yet</p>
            <p className="text-slate-600 text-sm mt-1">
              Make your first prediction to see it here
            </p>
            <Button className="mt-4" asChild>
              <Link href="/predict">Make a prediction</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
