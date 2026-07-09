import type { Metadata } from "next";
import { Brain } from "lucide-react";
import { PredictView } from "@/components/predictions/predict-view";

export const metadata: Metadata = {
  title: "Predict a Match",
  description: "Get an AI-powered FIFA World Cup 2026 match prediction with full explainability.",
};

export default function PredictPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
          <Brain className="h-6 w-6 text-primary" aria-hidden="true" />
          AI Match Prediction
        </h1>
        <p className="mt-1 text-sm text-fg-muted">
          Select two teams and let the model predict the outcome
        </p>
      </div>
      <PredictView />
    </div>
  );
}
