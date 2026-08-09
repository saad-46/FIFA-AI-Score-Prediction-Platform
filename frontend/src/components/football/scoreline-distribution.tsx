import { Target } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ScorelineProbability } from "@/types";

interface ScorelineDistributionProps {
  scorelines: ScorelineProbability[];
  mostLikelyScore?: string;
}

/** The Poisson-derived scoreline probability distribution — server-renderable. */
export function ScorelineDistribution({ scorelines, mostLikelyScore }: ScorelineDistributionProps) {
  if (scorelines.length === 0) return null;
  const max = Math.max(...scorelines.map((s) => s.probability));

  return (
    <Card>
      <CardHeader className="pb-2 border-b border-border/20">
        <CardTitle className="flex items-center gap-2 font-mono text-xs tracking-wider uppercase text-foreground">
          <Target className="h-4.5 w-4.5 text-primary" aria-hidden="true" />
          Poisson Scoreline Probability Cluster
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {scorelines.map((s) => {
          const isTopPick = s.score === mostLikelyScore;
          return (
            <div key={s.score} className="flex items-center gap-3">
              <span className="w-10 shrink-0 font-mono text-sm font-semibold text-foreground">
                {s.score}
              </span>
              <div
                role="progressbar"
                aria-valuenow={Math.round(s.probability * 100)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${s.score} probability`}
                className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2"
              >
                <div
                  className="h-full rounded-full bg-accent transition-all duration-700 ease-out"
                  style={{ width: `${(s.probability / max) * 100}%` }}
                />
              </div>
              <span className="w-12 shrink-0 text-right text-xs text-fg-muted">
                {(s.probability * 100).toFixed(1)}%
              </span>
              {isTopPick && (
                <Badge variant="default" className="shrink-0">
                  Top pick
                </Badge>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
