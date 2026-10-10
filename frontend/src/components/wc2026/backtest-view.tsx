"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Check, X, History } from "lucide-react";
import { useBacktest } from "@/hooks/use-wc2026";
import { getApiErrorMessage } from "@/lib/api/client";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { asPercent, stageLabel } from "@/lib/wc2026";
import type { BacktestMatch, BacktestStageAccuracy } from "@/types";

/**
 * "Model vs Reality" — how the frozen model actually did across WC2026.
 *
 * This is a **historical evaluation**, not a forecast, and the UI says so
 * prominently: the model was frozen before any 2026 result was compared
 * against it. Every number here is read from the backend's scorecard; none is
 * recomputed or rounded into something more flattering.
 */
export function BacktestView() {
  const { data, error, isLoading, mutate } = useBacktest();
  const reduceMotion = useReducedMotion();
  const [filter, setFilter] = useState<"all" | "correct" | "missed">("all");

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-48 w-full rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        title="Couldn't load the backtest"
        description={getApiErrorMessage(error)}
        onRetry={() => mutate()}
      />
    );
  }

  if (!data) return null;

  const missed = (data.n_matches_scored ?? 0) - data.correct;
  const matches = data.matches.filter((match) =>
    filter === "all" ? true : filter === "correct" ? match.correct : !match.correct
  );

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="text-[11px] font-semibold uppercase tracking-wider">
            <History className="mr-1 h-3 w-3" aria-hidden="true" />
            WC2026 Backtest
          </Badge>
          {data.model_version && (
            <span className="text-xs text-fg-subtle">{data.model_version}</span>
          )}
        </div>
        <p className="max-w-2xl text-sm text-fg-muted">
          A historical evaluation, not a forecast. The model was frozen before any 2026 result was
          compared against it, and this scorecard never fed back into it.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryStat
          label="Result accuracy"
          value={asPercent(data.accuracy)}
          sub={`${data.correct} of ${data.n_matches_scored} matches`}
          accent
        />
        <SummaryStat label="Correct" value={String(data.correct)} sub="matches called right" />
        <SummaryStat label="Missed" value={String(missed)} sub="matches called wrong" />
        <SummaryStat
          label="Champion"
          value={data.actual_champion ?? "—"}
          sub={
            data.predicted_champion && data.predicted_champion !== data.actual_champion
              ? `Model picked ${data.predicted_champion}`
              : "Model called it"
          }
        />
      </div>

      <section className="space-y-3">
        <h2 className="eyebrow">
          Accuracy by stage
        </h2>
        <div className="space-y-2">
          {data.by_stage.map((stage, index) => (
            <StageBar
              key={stage.stage}
              stage={stage}
              index={index}
              reduceMotion={Boolean(reduceMotion)}
            />
          ))}
        </div>
        <p className="text-xs text-fg-subtle">
          Later stages carry very few matches — a single semi-final miss is 50% of that stage.
          Read the small samples with that in mind.
        </p>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="eyebrow">
            Match ledger
          </h3>
          <div className="flex gap-1.5" role="group" aria-label="Filter matches">
            {(["all", "correct", "missed"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                aria-pressed={filter === value}
                className={cn(
                  "rounded-md border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  filter === value
                    ? "border-primary bg-primary/15 text-foreground"
                    : "border-border bg-surface text-fg-muted hover:text-foreground"
                )}
              >
                {value}
              </button>
            ))}
          </div>
        </div>

        <div
          className="overflow-x-auto rounded-lg border border-border bg-surface"
          tabIndex={0}
          role="region"
          aria-label="Match-by-match ledger table"
        >
          <table className="w-full min-w-[560px] text-xs">
            <caption className="sr-only">
              Every WC2026 match with the frozen model&apos;s prediction and the actual result
            </caption>
            <thead>
              <tr className="border-b border-border eyebrow">
                <th scope="col" className="px-3 py-2 text-left font-normal">Match</th>
                <th scope="col" className="px-2 py-2 text-left font-normal">Stage</th>
                <th scope="col" className="px-2 py-2 text-left font-normal">Predicted</th>
                <th scope="col" className="px-2 py-2 text-left font-normal">Actual</th>
                <th scope="col" className="px-2 py-2 text-right font-normal">Score</th>
                <th scope="col" className="px-3 py-2 text-right font-normal">Call</th>
              </tr>
            </thead>
            <tbody>
              {matches.map((match) => (
                <LedgerRow key={`${match.match_number}-${match.match}`} match={match} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-fg-subtle">
          Showing {matches.length} of {data.n_matches_scored} matches
        </p>
      </section>
    </div>
  );
}

function SummaryStat({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-3">
      <p className="eyebrow">{label}</p>
      <p
        className={cn(
          "truncate pt-1 text-2xl font-bold tabular-nums",
          accent ? "text-primary" : "text-foreground"
        )}
      >
        {value}
      </p>
      <p className="pt-0.5 text-[11px] text-fg-muted">{sub}</p>
    </div>
  );
}

function StageBar({
  stage,
  index,
  reduceMotion,
}: {
  stage: BacktestStageAccuracy;
  index: number;
  reduceMotion: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 truncate text-xs text-fg-muted">{stageLabel(stage.stage)}</span>
      <div
        role="progressbar"
        aria-valuenow={Math.round(stage.accuracy * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${stageLabel(stage.stage)} accuracy`}
        className="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-2"
      >
        <motion.div
          className="h-full rounded-full bg-primary"
          initial={reduceMotion ? false : { width: 0 }}
          animate={{ width: `${stage.accuracy * 100}%` }}
          transition={{
            duration: 0.5,
            ease: "easeOut",
            delay: reduceMotion ? 0 : index * 0.05,
          }}
        />
      </div>
      <span className="w-11 shrink-0 text-right font-mono text-xs tabular-nums text-foreground">
        {asPercent(stage.accuracy)}
      </span>
      <span className="w-12 shrink-0 text-right font-mono text-[10px] tabular-nums text-fg-muted">
        {stage.correct}/{stage.total}
      </span>
    </div>
  );
}

function LedgerRow({ match }: { match: BacktestMatch }) {
  return (
    <tr className="border-b border-border/40 last:border-0 transition-colors hover:bg-surface-2/50">
      <th scope="row" className="px-3 py-1.5 text-left font-normal text-foreground">
        {match.match}
      </th>
      <td className="px-2 py-1.5 eyebrow">
        {stageLabel(match.stage)}
      </td>
      <td className="px-2 py-1.5 text-fg-muted">{match.predicted ?? "—"}</td>
      <td className="px-2 py-1.5 text-foreground">{match.actual ?? "—"}</td>
      <td className="px-2 py-1.5 text-right font-mono text-[11px] tabular-nums text-fg-muted">
        {match.actual_score ?? "—"}
      </td>
      <td className="px-3 py-1.5 text-right">
        <span
          className={cn(
            "inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider",
            match.correct ? "text-win" : "text-loss"
          )}
        >
          {match.correct ? (
            <Check className="h-3 w-3" aria-hidden="true" />
          ) : (
            <X className="h-3 w-3" aria-hidden="true" />
          )}
          {match.correct ? "Hit" : "Miss"}
        </span>
      </td>
    </tr>
  );
}
