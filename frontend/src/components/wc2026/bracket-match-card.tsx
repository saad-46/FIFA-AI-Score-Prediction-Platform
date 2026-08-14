"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { predictionOutcome, sideScores, sourceLabel, scoreQualifier } from "@/lib/wc2026";
import type { BracketNodeData } from "@/types";

interface BracketMatchCardProps {
  node: BracketNodeData;
  /** True when this match is part of the currently hovered progression path. */
  highlighted?: boolean;
  /** True when some other path is hovered — this one dims back. */
  dimmed?: boolean;
  onHover?: (matchNumber: number | null) => void;
  onSelect?: (node: BracketNodeData) => void;
  className?: string;
}

/**
 * One fixture in the bracket.
 *
 * Solid surface rather than glass by deliberate choice: the bracket is a dense
 * data region where dozens of these tile together, and translucent panels
 * stacked at that density cost legibility for no gain. Glass is reserved for
 * the floating detail dialog that opens on top of it.
 */
export function BracketMatchCard({
  node,
  highlighted = false,
  dimmed = false,
  onHover,
  onSelect,
  className,
}: BracketMatchCardProps) {
  const reduceMotion = useReducedMotion();
  const scores = sideScores(node);
  const qualifier = scoreQualifier(node);
  const outcome = predictionOutcome(node);
  const isCompleted = node.status === "completed";

  const homeWon = isCompleted && node.winner_team !== null && node.winner_team === node.home_team;
  const awayWon = isCompleted && node.winner_team !== null && node.winner_team === node.away_team;

  const label = `Match ${node.match_number}: ${node.home_team ?? sourceLabel(node.home_source)} versus ${
    node.away_team ?? sourceLabel(node.away_source)
  }`;

  return (
    <motion.button
      type="button"
      aria-label={label}
      onClick={() => onSelect?.(node)}
      onMouseEnter={() => onHover?.(node.match_number)}
      onMouseLeave={() => onHover?.(null)}
      onFocus={() => onHover?.(node.match_number)}
      onBlur={() => onHover?.(null)}
      whileHover={reduceMotion ? undefined : { y: -2 }}
      transition={{ duration: 0.15, ease: "easeOut" }}
      className={cn(
        "group w-full overflow-hidden rounded-lg border bg-surface text-left",
        "transition-colors duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        highlighted
          ? "border-primary/60 shadow-[0_0_0_1px_var(--primary)]"
          : "border-border hover:border-primary/40",
        dimmed && "opacity-40",
        className
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-border/60 bg-surface-2/60 px-2.5 py-1">
        <span className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">
          {node.group ? node.group : `Match ${node.match_number}`}
        </span>
        {outcome !== null && (
          <span
            title={outcome ? "Model called this correctly" : "Model missed this one"}
            className={cn(
              "flex items-center gap-0.5 font-mono text-[10px]",
              outcome ? "text-win" : "text-loss"
            )}
          >
            {outcome ? (
              <Check className="h-3 w-3" aria-hidden="true" />
            ) : (
              <X className="h-3 w-3" aria-hidden="true" />
            )}
            <span className="sr-only">
              {outcome ? "Prediction correct" : "Prediction incorrect"}
            </span>
          </span>
        )}
      </header>

      <TeamRow
        name={node.home_team}
        fallback={sourceLabel(node.home_source)}
        score={scores.home}
        won={homeWon}
      />
      <div className="h-px bg-border/60" />
      <TeamRow
        name={node.away_team}
        fallback={sourceLabel(node.away_source)}
        score={scores.away}
        won={awayWon}
      />

      {qualifier && (
        <p className="border-t border-border/60 px-2.5 py-0.5 text-right font-mono text-[9px] uppercase tracking-wider text-fg-muted">
          {qualifier}
        </p>
      )}
    </motion.button>
  );
}

function TeamRow({
  name,
  fallback,
  score,
  won,
}: {
  name: string | null;
  fallback: string;
  score: number | null;
  won: boolean;
}) {
  return (
    <div className={cn("flex items-center justify-between gap-2 px-2.5 py-1.5", won && "bg-primary/10")}>
      <span
        className={cn(
          "truncate text-xs",
          name ? (won ? "font-semibold text-foreground" : "text-foreground/80") : "italic text-fg-muted"
        )}
      >
        {name ?? fallback}
      </span>
      {score !== null && (
        <span
          className={cn(
            "shrink-0 font-mono text-xs tabular-nums",
            won ? "font-bold text-primary" : "text-fg-muted"
          )}
        >
          {score}
        </span>
      )}
    </div>
  );
}
