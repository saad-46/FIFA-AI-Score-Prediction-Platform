import type { Metadata } from "next";
import { Brain } from "lucide-react";
import { PredictView } from "@/components/predictions/predict-view";

export const metadata: Metadata = {
  title: "Simulation Engine",
  description: "Execute Poisson-derived match simulations and SHAP explainability matrices.",
};

export default function PredictPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-foreground font-mono uppercase">
          <Brain className="h-6 w-6 text-primary" aria-hidden="true" />
          Simulation Engine
        </h1>
        <p className="mt-1 text-sm text-fg-muted">
          Configure model parameters to execute Poisson-derived predictive scoreline vectors
        </p>
      </div>
      <PredictView />
    </div>
  );
}
