"use client";

import { useState } from "react";
import { Brain } from "lucide-react";
import { PredictionForm } from "@/components/predictions/prediction-form";
import { PredictionResultCard } from "@/components/predictions/prediction-result";
import { ReasoningLoader } from "@/components/predictions/reasoning-loader";
import { EmptyState } from "@/components/ui/empty-state";
import { useUser } from "@/hooks/use-user";
import type { PredictionResult } from "@/types";

export function PredictView() {
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const { isAuthenticated } = useUser();

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 items-start">
      <div>
        <PredictionForm
          onResult={(res) => {
            setResult(res);
            setLoading(false);
          }}
          onStartPredict={() => {
            setResult(null);
            setLoading(true);
          }}
          onPredictError={() => {
            setLoading(false);
          }}
        />
      </div>
      <div className="sticky top-24">
        {loading ? (
          <ReasoningLoader />
        ) : result ? (
          <PredictionResultCard result={result} isAuthenticated={isAuthenticated} />
        ) : (
          <div className="flex h-full min-h-[400px] flex-col items-center justify-center rounded-xl border border-dashed border-border/40 bg-zinc-950/20 backdrop-blur-sm p-8 text-center">
            <EmptyState
              icon={Brain}
              title="Simulation Output Panel"
              description='Configure the model parameters on the left pane and execute "Run Simulation" to retrieve prediction data.'
            />
          </div>
        )}
      </div>
    </div>
  );
}
