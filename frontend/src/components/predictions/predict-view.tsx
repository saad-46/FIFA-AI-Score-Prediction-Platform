"use client";

import { useState } from "react";
import { Brain } from "lucide-react";
import { PredictionForm } from "@/components/predictions/prediction-form";
import { PredictionResultCard } from "@/components/predictions/prediction-result";
import { EmptyState } from "@/components/ui/empty-state";
import { useUser } from "@/hooks/use-user";
import type { PredictionResult } from "@/types";

export function PredictView() {
  const [result, setResult] = useState<PredictionResult | null>(null);
  const { isAuthenticated } = useUser();

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
      <div>
        <PredictionForm onResult={setResult} />
      </div>
      <div>
        {result ? (
          <PredictionResultCard result={result} isAuthenticated={isAuthenticated} />
        ) : (
          <div className="flex h-full min-h-[400px] items-center justify-center rounded-xl border border-dashed border-border">
            <EmptyState
              icon={Brain}
              title="Prediction will appear here"
              description='Select two teams and click "Predict Match" to get started.'
            />
          </div>
        )}
      </div>
    </div>
  );
}
