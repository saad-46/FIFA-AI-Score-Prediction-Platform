import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Brain, BarChart3, Trophy, Shield, Zap, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MarketingHeader } from "@/components/layout/marketing-header";
import { Footer } from "@/components/layout/footer";

export const metadata: Metadata = {
  title: "FIFA AI — World Cup 2026 Score Predictions",
  description:
    "AI-powered FIFA World Cup 2026 match predictions using XGBoost, Elo ratings, and Monte Carlo tournament simulation — with full explainability.",
};

// Real, verifiable facts about the WC2026 tournament format itself — not
// fabricated engagement metrics. See KNOWN_ASSUMPTIONS / handoff Section 6.
const TOURNAMENT_FACTS = [
  { value: "48", label: "Teams competing" },
  { value: "12", label: "Groups" },
  { value: "104", label: "Total matches" },
  { value: "134", label: "ML features per prediction" },
];

const FEATURES = [
  {
    icon: Brain,
    title: "AI Score Prediction",
    description:
      "XGBoost regressors and a classifier trained on World Cup-era matches predict scorelines and win probabilities — with SHAP explainability on every result.",
  },
  {
    icon: Target,
    title: "Expected Goals (xG)",
    description:
      "A Poisson scoreline model built on each team's rolling form, dynamic Elo, and FIFA ranking differential.",
  },
  {
    icon: Trophy,
    title: "Tournament Simulation",
    description:
      "Monte Carlo simulation of the full 48-team bracket — aware of real, already-played 2026 results, not a blind hypothetical.",
  },
  {
    icon: Shield,
    title: "Head-to-Head History",
    description: "Full historical record for any two teams that have met in World Cup play.",
  },
  {
    icon: BarChart3,
    title: "Deep Analytics",
    description: "Scoreline frequency, model accuracy, and feature-importance breakdowns — honestly labeled where data is limited.",
  },
  {
    icon: Zap,
    title: "Explainable, Not a Black Box",
    description: "Every prediction shows its reasoning — the top factors driving the model's call, not just a number.",
  },
] as const;

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <MarketingHeader />

      <section className="relative overflow-hidden py-24 sm:py-32">
        <div className="absolute inset-0 -z-10" aria-hidden="true">
          <div className="absolute top-1/4 left-1/2 h-[600px] w-[600px] -translate-x-1/2 rounded-full bg-primary/5 blur-3xl" />
          <div className="absolute top-1/3 left-1/4 h-[400px] w-[400px] rounded-full bg-accent/5 blur-3xl" />
        </div>

        <div className="mx-auto max-w-7xl px-4 text-center sm:px-6 lg:px-8">
          <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-1.5 text-sm text-primary">
            <Zap className="h-3.5 w-3.5" aria-hidden="true" />
            FIFA World Cup 2026 — explainable AI predictions
          </div>

          <h1 className="mb-6 text-4xl font-black leading-tight text-foreground sm:text-6xl lg:text-7xl">
            See who wins —
            <br />
            <span className="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
              and why
            </span>
          </h1>

          <p className="mx-auto mb-10 max-w-2xl text-lg text-fg-muted">
            Machine learning trained specifically on World Cup-era football. Win probabilities,
            expected goals, and a full Monte Carlo tournament outlook — every prediction shows its
            reasoning.
          </p>

          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button size="xl" variant="gradient" asChild>
              <Link href="/predict">
                Predict a match
                <ArrowRight className="h-5 w-5" />
              </Link>
            </Button>
            <Button size="xl" variant="outline" asChild>
              <Link href="/tournaments">Explore the tournament</Link>
            </Button>
          </div>

          <div className="mx-auto mt-16 grid max-w-3xl grid-cols-2 gap-6 sm:grid-cols-4">
            {TOURNAMENT_FACTS.map((fact) => (
              <div key={fact.label} className="text-center">
                <p className="font-mono text-3xl font-black text-foreground">{fact.value}</p>
                <p className="mt-1 text-sm text-fg-muted">{fact.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-border py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-14 text-center">
            <h2 className="mb-4 text-3xl font-bold text-foreground">
              Everything you need to predict matches
            </h2>
            <p className="mx-auto max-w-xl text-fg-muted">
              From raw historical data to actionable, explained AI insights — all in one platform.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature) => {
              const Icon = feature.icon;
              return (
                <div
                  key={feature.title}
                  className="rounded-xl border border-border bg-surface/50 p-6 transition-colors hover:border-fg-muted/40"
                >
                  <div className="mb-4 inline-flex rounded-lg border border-primary/20 bg-primary/10 p-2.5 text-primary">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <h3 className="mb-2 font-semibold text-foreground">{feature.title}</h3>
                  <p className="text-sm text-fg-muted">{feature.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="border-t border-border py-20">
        <div className="mx-auto max-w-3xl px-4 text-center">
          <h2 className="mb-4 text-3xl font-bold text-foreground">
            Ready to predict your first match?
          </h2>
          <p className="mb-8 text-fg-muted">Free to use. No credit card required.</p>
          <Button size="xl" variant="gradient" asChild>
            <Link href="/predict">
              Start predicting
              <ArrowRight className="h-5 w-5" />
            </Link>
          </Button>
        </div>
      </section>

      <Footer />
    </div>
  );
}
