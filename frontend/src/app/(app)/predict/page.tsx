"use client";

import React, { useState } from "react";
import { Brain } from "lucide-react";
import { PredictionForm } from "@/components/predictions/prediction-form";
import { PredictionResultCard } from "@/components/predictions/prediction-result";
import type { PredictionResult } from "@/types";

export default function PredictPage() {
  const [result, setResult] = useState<PredictionResult | null>(null);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Brain className="h-6 w-6 text-emerald-400" />
          AI Match Prediction
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Select two teams and let our XGBoost model predict the outcome
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div>
          <PredictionForm onResult={setResult} />
        </div>
        <div>
          {result ? (
            <PredictionResultCard result={result} isAuthenticated={false} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full min-h-[400px] rounded-xl border border-dashed border-slate-700 text-center p-8">
              <Brain className="h-16 w-16 text-slate-700 mb-4" />
              <p className="text-slate-400 font-medium">
                Prediction will appear here
              </p>
              <p className="text-slate-600 text-sm mt-2">
                Select teams and click &quot;Predict Match&quot; to get started
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
