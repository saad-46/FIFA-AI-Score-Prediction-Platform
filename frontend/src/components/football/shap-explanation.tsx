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
      <CardHeader className="border-b border-border pb-3">
        <CardTitle className="flex items-center gap-2 font-display text-lg font-semibold uppercase tracking-wide text-foreground">
          What drove the prediction
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        <p className="text-xs leading-relaxed text-fg-subtle">
          Each bar is one input&apos;s contribution to the predicted result (SHAP values). Longer means more
          influence; the exact value is in the tooltip.
        </p>
        <TooltipProvider delayDuration={200}>
          {top_positive_features.length > 0 && (
            <div className="space-y-1.5">
              <p className="eyebrow">Pushed towards the predicted result</p>
              {top_positive_features.map((f) => (
                <FeatureRow key={f.feature} feature={f} maxImpact={maxImpact} tone="win" />
              ))}
            </div>
          )}
          {top_negative_features.length > 0 && (
            <div className="space-y-1.5 pt-2">
              <p className="eyebrow">Pulled against it</p>
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
        <div tabIndex={0} className="flex cursor-default items-center gap-2 rounded text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <span className="w-36 shrink-0 truncate text-right text-fg-muted">
            {feature.readable_name}
          </span>
          <div className="h-3.5 flex-1 overflow-hidden rounded bg-surface-2">
            <div
              // Cyan for, grey against: this is model attribution, not a good or
              // bad outcome, so win-green and loss-red would mislead.
              className={tone === "win" ? "h-full rounded bg-primary" : "h-full rounded bg-draw"}
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
