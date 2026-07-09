import { Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import type { FeatureAttribution, PredictionExplanation } from "@/types";

interface ShapExplanationProps {
  explanation: PredictionExplanation;
}

/** Signed SHAP feature-attribution bars — the "why" behind a prediction.
 * This is the explainability payload the app is built around; it was
 * previously dropped from the UI entirely despite being returned by the API. */
export function ShapExplanation({ explanation }: ShapExplanationProps) {
  const { top_positive_features, top_negative_features } = explanation;
  if (top_positive_features.length === 0 && top_negative_features.length === 0) return null;
  const maxImpact = Math.max(
    ...top_positive_features.map((f) => Math.abs(f.impact)),
    ...top_negative_features.map((f) => Math.abs(f.impact)),
    0.0001
  );

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-draw" aria-hidden="true" />
          Why this prediction
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <TooltipProvider delayDuration={200}>
          {top_positive_features.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-win">Favors this outcome</p>
              {top_positive_features.map((f) => (
                <FeatureRow key={f.feature} feature={f} maxImpact={maxImpact} tone="win" />
              ))}
            </div>
          )}
          {top_negative_features.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-loss">Works against it</p>
              {top_negative_features.map((f) => (
                <FeatureRow key={f.feature} feature={f} maxImpact={maxImpact} tone="loss" />
              ))}
            </div>
          )}
        </TooltipProvider>
      </CardContent>
    </Card>
  );
}

function FeatureRow({
  feature,
  maxImpact,
  tone,
}: {
  feature: FeatureAttribution;
  maxImpact: number;
  tone: "win" | "loss";
}) {
  const widthPct = (Math.abs(feature.impact) / maxImpact) * 100;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center gap-2 text-xs cursor-default">
          <span className="w-36 shrink-0 truncate text-right text-fg-muted">
            {feature.readable_name}
          </span>
          <div className="h-3.5 flex-1 overflow-hidden rounded bg-surface-2">
            <div
              className={tone === "win" ? "h-full rounded bg-win/70" : "h-full rounded bg-loss/70"}
              style={{ width: `${widthPct}%` }}
            />
          </div>
        </div>
      </TooltipTrigger>
      <TooltipContent>
        {feature.readable_name}: {feature.impact > 0 ? "+" : ""}
        {feature.impact.toFixed(4)}
      </TooltipContent>
    </Tooltip>
  );
}
