import type { Metadata } from "next";
import { Brain, AlertTriangle, Layers } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const metadata: Metadata = {
  title: "About",
  description: "How the FIFA AI prediction model works, and its honest limitations.",
};

const STACK = [
  "XGBoost (Poisson regressors + softmax classifier)",
  "Dynamic, tournament-weighted Elo ratings",
  "Poisson scoreline simulation",
  "Monte Carlo tournament simulation",
  "SHAP feature explainability",
  "FastAPI + async SQLAlchemy + Supabase Postgres",
];

export default function AboutPage() {
  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
          <Brain className="h-6 w-6 text-primary" aria-hidden="true" />
          About
        </h1>
        <p className="mt-1 text-sm text-fg-muted">How the model works, and where it falls short</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-accent" aria-hidden="true" />
            Methodology
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-fg-muted">
          <p>
            Two XGBoost regressors predict each team&apos;s expected goals; a classifier predicts
            win/draw/loss probability. A Poisson model turns expected goals into a full scoreline
            distribution. Outcome probabilities blend the Poisson-derived and classifier-derived
            results. A dynamic Elo rating (tournament-weighted, computed chronologically with no
            future data leakage) and FIFA ranking differential are among the ~134 engineered
            features. Every prediction includes SHAP attributions so the reasoning is visible, not
            just the number.
          </p>
          <p>
            The World Cup 2026 tournament simulator runs thousands of Monte Carlo simulations of
            the full 48-team bracket using this same model for every hypothetical matchup — already
            -played 2026 matches use their real recorded result rather than being re-simulated.
          </p>
          <div className="flex flex-wrap gap-1.5 pt-2">
            {STACK.map((item) => (
              <Badge key={item} variant="secondary">
                {item}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-draw" aria-hidden="true" />
            Honest limitations
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-fg-muted">
          <p>
            The model is trained on a deliberately narrow, World-Cup-only dataset (roughly 400
            matches) — relevant, but small. Treat outputs as directional, not laboratory-precise.
          </p>
          <p>
            The draw-prediction calibration trades precision for recall and may over-call draws in
            some matchups — a known, open tradeoff, not a bug.
          </p>
          <p>
            Goal-distribution-by-minute charts on the Analytics page are placeholder/sample data —
            no real minute-level goal data exists in the dataset yet, and this is always labeled
            honestly rather than hidden.
          </p>
          <p>This platform is for entertainment and analysis purposes only, and is not affiliated with FIFA.</p>
        </CardContent>
      </Card>
    </div>
  );
}
