import type { Metadata } from "next";
import { PredictView } from "@/components/predictions/predict-view";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = {
  title: "Match predictor",
  description: "Pick two national teams and a venue for win, draw and loss probabilities, expected goals and the most likely scorelines.",
};

export default function PredictPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Match predictor"
        description="Set up a fixture between any two of the 48 World Cup teams. You get the probability of each result, expected goals and the likeliest scorelines."
      />
      <PredictView />
    </div>
  );
}
