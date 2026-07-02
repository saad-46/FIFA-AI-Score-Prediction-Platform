import Link from "next/link";
import { ArrowRight, Brain, BarChart3, Trophy, Shield, Zap, Target } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-950">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/90 backdrop-blur-md sticky top-0 z-50">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex h-16 items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500">
              <Trophy className="h-4 w-4 text-white" />
            </div>
            <span className="text-lg font-bold text-white">
              FIFA<span className="text-emerald-400">AI</span>
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/auth/login">Sign in</Link>
            </Button>
            <Button size="sm" variant="gradient" asChild>
              <Link href="/auth/register">Get started free</Link>
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden py-24 sm:py-32">
        {/* Background glow */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-1/4 left-1/2 -translate-x-1/2 h-[600px] w-[600px] rounded-full bg-emerald-500/5 blur-3xl" />
          <div className="absolute top-1/3 left-1/4 h-[400px] w-[400px] rounded-full bg-cyan-500/5 blur-3xl" />
        </div>

        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-sm text-emerald-400 mb-8">
            <Zap className="h-3.5 w-3.5" />
            Powered by XGBoost ML
          </div>

          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-black text-white leading-tight mb-6">
            Predict Football
            <br />
            <span className="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
              Scores with AI
            </span>
          </h1>

          <p className="mx-auto max-w-2xl text-lg text-slate-400 mb-10">
            Advanced machine learning trained on decades of FIFA match data.
            Get win probabilities, expected goals, and deep team analytics
            before every match.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button size="xl" variant="gradient" asChild>
              <Link href="/auth/register">
                Start predicting free
                <ArrowRight className="h-5 w-5" />
              </Link>
            </Button>
            <Button size="xl" variant="outline" asChild>
              <Link href="/dashboard">View demo</Link>
            </Button>
          </div>

          {/* Stats row */}
          <div className="mt-16 grid grid-cols-2 sm:grid-cols-4 gap-6 max-w-3xl mx-auto">
            {[
              { value: "44K+", label: "Matches analyzed" },
              { value: "300+", label: "Teams tracked" },
              { value: "78%", label: "Prediction accuracy" },
              { value: "150+", label: "Tournaments" },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <p className="text-3xl font-black text-white">{stat.value}</p>
                <p className="text-sm text-slate-500 mt-1">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 border-t border-slate-800">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-white mb-4">
              Everything you need to predict matches
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto">
              From raw historical data to actionable AI insights — all in one platform.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: Brain,
                title: "AI Score Prediction",
                description:
                  "XGBoost model trained on 44,000+ historical matches predicts exact scores and win probabilities.",
                color: "emerald",
              },
              {
                icon: Target,
                title: "Expected Goals (xG)",
                description:
                  "Poisson regression models calculate expected goals for each team based on historical attack/defense metrics.",
                color: "cyan",
              },
              {
                icon: BarChart3,
                title: "Deep Analytics",
                description:
                  "Goal distribution charts, scoreline frequencies, tournament stats, and team performance trends.",
                color: "purple",
              },
              {
                icon: Shield,
                title: "Head-to-Head History",
                description:
                  "Complete historical record of every matchup between any two teams in the database.",
                color: "amber",
              },
              {
                icon: Trophy,
                title: "Tournament Analytics",
                description:
                  "World Cup, Euros, Copa America — deep stats for every major tournament.",
                color: "red",
              },
              {
                icon: Zap,
                title: "AI Insights",
                description:
                  "Natural language insights explaining why the model made each prediction.",
                color: "emerald",
              },
            ].map((feature) => {
              const Icon = feature.icon;
              const colorClasses: Record<string, string> = {
                emerald: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
                cyan: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
                purple: "bg-purple-500/10 text-purple-400 border-purple-500/20",
                amber: "bg-amber-500/10 text-amber-400 border-amber-500/20",
                red: "bg-red-500/10 text-red-400 border-red-500/20",
              };
              return (
                <div
                  key={feature.title}
                  className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 hover:border-slate-700 transition-colors"
                >
                  <div
                    className={`inline-flex rounded-lg border p-2.5 mb-4 ${colorClasses[feature.color]}`}
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="font-semibold text-slate-100 mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-sm text-slate-400">{feature.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 border-t border-slate-800">
        <div className="mx-auto max-w-3xl px-4 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to predict your first match?
          </h2>
          <p className="text-slate-400 mb-8">
            Free to start. No credit card required.
          </p>
          <Button size="xl" variant="gradient" asChild>
            <Link href="/auth/register">
              Create free account
              <ArrowRight className="h-5 w-5" />
            </Link>
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-8">
        <div className="mx-auto max-w-7xl px-4 text-center text-xs text-slate-600">
          © 2025 FIFA AI. For entertainment purposes only. Not affiliated with FIFA.
        </div>
      </footer>
    </div>
  );
}
