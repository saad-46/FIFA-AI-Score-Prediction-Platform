"use client";

import { motion, useReducedMotion } from "framer-motion";
import { CalendarDays, MapPin, Check, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  asPercent,
  formatMatchDate,
  formatScore,
  predictionOutcome,
  scoreQualifier,
  sourceLabel,
  stageLabel,
} from "@/lib/wc2026";
import type { BracketNodeData, Wc2026TeamMeta } from "@/types";

interface MatchDetailDialogProps {
  node: BracketNodeData | null;
  teams?: Record<string, Wc2026TeamMeta>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Detail panel for a single fixture — opened from the bracket or a group
 * fixture list rather than navigating away, so the user keeps their place.
 *
 * This is one of the few surfaces where glass is used: it floats above the
 * dense bracket, and the translucency keeps the bracket legible underneath as
 * context. Everything inside it stays on solid, high-contrast type.
 */
export function MatchDetailDialog({ node, teams, open, onOpenChange }: MatchDetailDialogProps) {
  const reduceMotion = useReducedMotion();
  if (!node) return null;

  const prediction = node.prediction;
  const outcome = predictionOutcome(node);
  const score = formatScore(node);
  const qualifier = scoreQualifier(node);
  const date = formatMatchDate(node.date);
  const homeMeta = node.home_team ? teams?.[node.home_team] : undefined;
  const awayMeta = node.away_team ? teams?.[node.away_team] : undefined;

  const home = node.home_team ?? sourceLabel(node.home_source);
  const away = node.away_team ?? sourceLabel(node.away_source);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg border-border/60 bg-surface/80 backdrop-blur-xl">
        <DialogHeader>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="font-mono text-[10px] uppercase tracking-wider">
              {stageLabel(node.stage)}
            </Badge>
            {node.group && (
              <Badge variant="secondary" className="font-mono text-[10px] uppercase tracking-wider">
                {node.group}
              </Badge>
            )}
            <span className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
              Match {node.match_number}
            </span>
          </div>
          <DialogTitle className="pt-1 text-lg">
            {home} <span className="text-fg-muted">v</span> {away}
          </DialogTitle>
          <DialogDescription className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px]">
            {date && (
              <span className="inline-flex items-center gap-1">
                <CalendarDays className="h-3 w-3" aria-hidden="true" />
                {date}
                {node.kickoff_time_et ? ` · ${node.kickoff_time_et} ET` : ""}
              </span>
            )}
            {node.city && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3 w-3" aria-hidden="true" />
                {node.city}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          {score && (
            <section className="rounded-lg border border-border/60 bg-surface-2/50 px-4 py-3 text-center">
              <p className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
                Final result
              </p>
              <p className="pt-0.5 font-mono text-3xl font-bold tabular-nums text-foreground">
                {score}
              </p>
              {qualifier && (
                <p className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
                  {qualifier}
                </p>
              )}
              {node.winner_team && (
                <p className="pt-1 text-xs text-fg-muted">
                  <span className="font-semibold text-foreground">{node.winner_team}</span> advanced
                </p>
              )}
            </section>
          )}

          {prediction && (
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
                  Model prediction
                </h3>
                {outcome !== null && (
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider",
                      outcome ? "text-win" : "text-loss"
                    )}
                  >
                    {outcome ? (
                      <Check className="h-3 w-3" aria-hidden="true" />
                    ) : (
                      <X className="h-3 w-3" aria-hidden="true" />
                    )}
                    {outcome ? "Correct" : "Missed"}
                  </span>
                )}
              </div>

              <OutcomeBars
                home={home}
                away={away}
                homeProb={prediction.home_win_probability}
                drawProb={prediction.draw_probability}
                awayProb={prediction.away_win_probability}
                reduceMotion={Boolean(reduceMotion)}
              />

              <div className="grid grid-cols-2 gap-3 pt-1">
                <Stat label="Predicted winner" value={prediction.predicted_winner ?? "—"} />
                <Stat label="Predicted score" value={prediction.most_likely_score ?? "—"} mono />
              </div>
              {prediction.predicted_home_goals !== null &&
                prediction.predicted_away_goals !== null && (
                  <p className="font-mono text-[10px] text-fg-muted">
                    Expected goals {prediction.predicted_home_goals.toFixed(2)} –{" "}
                    {prediction.predicted_away_goals.toFixed(2)}
                  </p>
                )}
            </section>
          )}

          {(homeMeta || awayMeta) && (
            <section className="space-y-2">
              <h3 className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
                Pre-tournament rating
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <TeamMetaBlock name={home} meta={homeMeta} />
                <TeamMetaBlock name={away} meta={awayMeta} />
              </div>
            </section>
          )}

          {prediction?.model_version && (
            <p className="border-t border-border/40 pt-3 font-mono text-[10px] text-fg-muted">
              {prediction.model_version} · prediction frozen before the tournament
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function OutcomeBars({
  home,
  away,
  homeProb,
  drawProb,
  awayProb,
  reduceMotion,
}: {
  home: string;
  away: string;
  homeProb: number | null;
  drawProb: number | null;
  awayProb: number | null;
  reduceMotion: boolean;
}) {
  const rows: Array<{ label: string; value: number | null; tone: string }> = [
    { label: home, value: homeProb, tone: "bg-primary" },
    { label: "Draw", value: drawProb, tone: "bg-draw" },
    { label: away, value: awayProb, tone: "bg-accent" },
  ];

  return (
    <div className="space-y-2">
      {rows.map((row) => (
        <div key={row.label} className="flex items-center gap-3">
          <span className="w-24 shrink-0 truncate text-xs text-fg-muted">{row.label}</span>
          <div
            role="progressbar"
            aria-valuenow={Math.round((row.value ?? 0) * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${row.label} probability`}
            className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2"
          >
            <motion.div
              className={cn("h-full rounded-full", row.tone)}
              initial={reduceMotion ? false : { width: 0 }}
              animate={{ width: `${(row.value ?? 0) * 100}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            />
          </div>
          <span className="w-9 shrink-0 text-right font-mono text-xs tabular-nums text-foreground">
            {asPercent(row.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

function Stat({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-lg border border-border/60 bg-surface-2/40 px-3 py-2">
      <p className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">{label}</p>
      <p className={cn("truncate pt-0.5 text-sm font-semibold text-foreground", mono && "font-mono tabular-nums")}>
        {value}
      </p>
    </div>
  );
}

function TeamMetaBlock({ name, meta }: { name: string; meta?: Wc2026TeamMeta }) {
  return (
    <div className="rounded-lg border border-border/60 bg-surface-2/40 px-3 py-2">
      <p className="truncate text-xs font-semibold text-foreground">{name}</p>
      <dl className="pt-1 space-y-0.5 font-mono text-[10px] text-fg-muted">
        <div className="flex justify-between gap-2">
          <dt>Elo</dt>
          <dd className="tabular-nums text-foreground/80">{meta?.elo_rating?.toFixed(0) ?? "—"}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>FIFA rank</dt>
          <dd className="tabular-nums text-foreground/80">{meta?.fifa_ranking ?? "—"}</dd>
        </div>
      </dl>
    </div>
  );
}
