"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ScorelineProbability } from "@/types";

interface ScorelineDistributionProps {
  scorelines: ScorelineProbability[];
  mostLikelyScore?: string;
}

/** How many rows to show. The API returns 10; beyond that the tail is a long
 * run of sub-1% scorelines that adds length without informing anything. */
const MAX_ROWS = 10;

/**
 * The Poisson-derived scoreline distribution.
 *
 * Bars are scaled to the most likely scoreline rather than to 100%, because
 * even the top pick is usually only ~15% — scaling to 100% would render every
 * row as a barely-visible sliver. The percentage label carries the true value,
 * so the bar is a comparison aid, not the number itself.
 *
 * Uses the cyan primary rather than the green accent: this is not a
 * good/bad outcome, and green here fought with the win/loss semantics used
 * elsewhere in the result.
 */
export function ScorelineDistribution({ scorelines, mostLikelyScore }: ScorelineDistributionProps) {
  const reduceMotion = useReducedMotion();
  if (scorelines.length === 0) return null;

  const rows = [...scorelines]
    .sort((a, b) => b.probability - a.probability)
    .slice(0, MAX_ROWS);
  const max = Math.max(...rows.map((s) => s.probability), 0.0001);
  const covered = rows.reduce((sum, s) => sum + s.probability, 0);

  return (
    <Card>
      <CardHeader className="border-b border-border pb-3">
        <CardTitle className="flex items-center gap-2 font-display text-lg font-semibold uppercase tracking-wide text-foreground">
          Likeliest scorelines
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1.5 pt-4">
        {rows.map((s, index) => {
          const isTopPick = s.score === mostLikelyScore || index === 0;
          const pct = s.probability * 100;
          return (
            <div
              key={s.score}
              className="group flex items-center gap-3 rounded px-1 py-0.5 transition-colors hover:bg-surface-2/50"
              title={`${s.score} — ${pct.toFixed(1)}%`}
            >
              <span
                className={cn(
                  "w-9 shrink-0 font-mono text-sm tabular-nums",
                  isTopPick ? "font-bold text-foreground" : "font-semibold text-fg-muted"
                )}
              >
                {s.score}
              </span>
              <div
                role="progressbar"
                aria-valuenow={Math.round(pct)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Scoreline ${s.score} probability`}
                className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2"
              >
                <motion.div
                  className={cn("h-full rounded-full", isTopPick ? "bg-primary" : "bg-primary/40")}
                  initial={reduceMotion ? false : { width: 0 }}
                  animate={{ width: `${(s.probability / max) * 100}%` }}
                  transition={{
                    duration: 0.5,
                    ease: "easeOut",
                    delay: reduceMotion ? 0 : index * 0.04,
                  }}
                />
              </div>
              <span
                className={cn(
                  "w-11 shrink-0 text-right font-mono text-xs tabular-nums",
                  isTopPick ? "text-foreground" : "text-fg-muted"
                )}
              >
                {pct.toFixed(1)}%
              </span>
              <span className="w-14 shrink-0 text-right">
                {isTopPick && (
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-primary">
                    Likeliest
                  </span>
                )}
              </span>
            </div>
          );
        })}

        <p className="pt-2 text-xs leading-relaxed text-fg-subtle">
          These {rows.length} scorelines cover {(covered * 100).toFixed(0)}% of all outcomes; the rest is spread over
          less likely scores. Bars are scaled to the likeliest one.
        </p>
      </CardContent>
    </Card>
  );
}
