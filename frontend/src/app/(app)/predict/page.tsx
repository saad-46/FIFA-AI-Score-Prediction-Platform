import type { Metadata } from "next";
import { Brain } from "lucide-react";
import { PredictView } from "@/components/predictions/predict-view";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = {
  title: "Simulation Engine",
  description: "Execute Poisson-derived match simulations and SHAP explainability matrices.",
};

export default function PredictPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        icon={Brain}
        title="Simulation Engine"
        description="Configure model parameters to execute Poisson-derived predictive scoreline vectors"
      />
      <PredictView />
    </div>
  );
}
