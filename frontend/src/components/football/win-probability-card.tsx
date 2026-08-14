"use client";

import { motion, useReducedMotion } from "framer-motion";
import { TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TeamFlag } from "@/components/football/team-flag";
import { cn } from "@/lib/utils";

interface WinProbabilityCardProps {
  homeTeam: string;
  awayTeam: string;
  homeWinProbability: number;
  drawProbability: number;
  awayWinProbability: number;
}

/**
 * Match outcome probabilities as flagged horizontal bars.
 *
 * Replaces a 160px donut that sat beside a duplicate set of bars — the donut
 * showed the same three numbers in a form that is harder to compare (arc
 * lengths read worse than aligned bars for a 3-way split) and cost most of the
 * card's width. One row per outcome, sorted by likelihood, so the model's pick
 * is the top line rather than something to hunt for.
 *
 * Colour: cyan primary for the two teams, muted for the draw. Deliberately not
 * win-green / loss-red — "home win" is not a good outcome and "away win" is not
 * a bad one, so semantic colour would be meaningless here.
 */
export function WinProbabilityCard({
  homeTeam,
  awayTeam,
  homeWinProbability,
  drawProbability,
  awayWinProbability,
}: WinProbabilityCardProps) {
  const reduceMotion = useReducedMotion();

  const rows = [
    { key: "home", label: homeTeam, value: homeWinProbability, isTeam: true },
    { key: "draw", label: "Draw", value: drawProbability, isTeam: false },
    { key: "away", label: awayTeam, value: awayWinProbability, isTeam: true },
  ].sort((a, b) => b.value - a.value);

  const leader = rows[0];

  return (
    <Card>
      <CardHeader className="pb-2 border-b border-border/20">
        <CardTitle className="flex items-center gap-2 font-mono text-xs tracking-wider uppercase text-foreground">
          <TrendingUp className="h-4.5 w-4.5 text-primary" aria-hidden="true" />
          Outcome Probability
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-4">
        {rows.map((row, index) => {
          const pct = row.value * 100;
          const isLeader = row.key === leader.key;
          return (
            <div key={row.key} className="space-y-1">
              <div className="flex items-center gap-2">
                {row.isTeam ? (
                  <TeamFlag name={row.label} size="sm" />
                ) : (
                  <span
                    aria-hidden="true"
                    className="inline-flex h-4 w-[1.4rem] shrink-0 items-center justify-center rounded-[2px] border border-border bg-surface-2 font-mono text-[8px] uppercase text-fg-muted"
                  >
                    ⁄
                  </span>
                )}
                <span
                  className={cn(
                    "min-w-0 flex-1 truncate text-xs",
                    isLeader ? "font-semibold text-foreground" : "text-fg-muted"
                  )}
                >
                  {row.label}
                </span>
                <span
                  className={cn(
                    "shrink-0 font-mono text-sm tabular-nums",
                    isLeader ? "font-bold text-primary" : "text-fg-muted"
                  )}
                >
                  {pct.toFixed(1)}%
                </span>
              </div>
              <div
                role="progressbar"
                aria-valuenow={Math.round(pct)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${row.label} probability`}
                title={`${row.label}: ${pct.toFixed(1)}%`}
                className="h-2.5 w-full overflow-hidden rounded-full bg-surface-2"
              >
                <motion.div
                  className={cn(
                    "h-full rounded-full",
                    isLeader ? "bg-primary" : row.isTeam ? "bg-primary/45" : "bg-draw"
                  )}
                  initial={reduceMotion ? false : { width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{
                    duration: 0.55,
                    ease: "easeOut",
                    delay: reduceMotion ? 0 : index * 0.07,
                  }}
                />
              </div>
            </div>
          );
        })}

        <p className="pt-1 font-mono text-[10px] uppercase tracking-wider text-fg-muted">
          Calibrated · sums to 100%
        </p>
      </CardContent>
    </Card>
  );
}
