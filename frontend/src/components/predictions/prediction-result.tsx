"use client";

import React, { useState } from "react";
import { AlertTriangle, BookmarkPlus, Check, Info, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { predictionsApi } from "@/lib/api/predictions";
import { getApiErrorMessage } from "@/lib/api/client";
import { toast } from "@/hooks/use-toast";
import { formatGoals, cn } from "@/lib/utils";
import { ScorelineDistribution } from "@/components/football/scoreline-distribution";
import { ShapExplanation } from "@/components/football/shap-explanation";
import { HeadToHeadCard } from "@/components/football/head-to-head-card";
import { TeamFlag } from "@/components/football/team-flag";
import { SectionHeader } from "@/components/ui/section";
import type { PredictionResult } from "@/types";

interface PredictionResultCardProps {
  result: PredictionResult;
  isAuthenticated: boolean;
}

const INSIGHT_ICON = { advantage: TrendingUp, warning: AlertTriangle, neutral: Info } as const;

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

/**
 * One match prediction.
 *
 * The header is a scoreboard: the two teams either side of the most likely
 * scoreline, and directly beneath it the three outcome probabilities on one
 * bar. Putting them together is deliberate. The most likely *scoreline* and the
 * most likely *result* are different questions — a 1–1 can be the single most
 * probable score while one side is still the likelier winner — and showing only
 * a big scoreline invites reading it as a verdict.
 *
 * No "confidence" read-out: the API's confidence_score measures how much match
 * history backs the prediction, not how likely it is to be right, and the
 * frontend contract keeps it out of the UI.
 */
export function PredictionResultCard({ result, isAuthenticated }: PredictionResultCardProps) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    if (saving || saved) return;
    setSaving(true);
    try {
      await predictionsApi.save(result.prediction_id);
      setSaved(true);
      toast({ title: "Prediction saved", description: "You can find it under your saved predictions.", variant: "success" });
    } catch (err) {
      toast({ title: "Couldn't save the prediction", description: getApiErrorMessage(err), variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const { home_team: home, away_team: away } = result;
  const pHome = result.home_win_probability;
  const pDraw = result.draw_probability;
  const pAway = result.away_win_probability;

  const outcomes = [
    { key: "home" as const, label: `${home} win`, value: pHome },
    { key: "draw" as const, label: "Draw", value: pDraw },
    { key: "away" as const, label: `${away} win`, value: pAway },
  ];
  const top = [...outcomes].sort((a, b) => b.value - a.value)[0];
  const second = [...outcomes].sort((a, b) => b.value - a.value)[1];
  const close = top.value - second.value < 0.05;

  const topScore = result.top_scorelines.find((s) => s.score === result.most_likely_score);
  const headline = close
    ? `Too close to call: ${top.label.toLowerCase()} ${pct(top.value)}, ${second.label.toLowerCase()} ${pct(second.value)}`
    : top.key === "draw"
      ? `A draw is the likeliest result, at ${pct(top.value)}`
      : `${top.key === "home" ? home : away} are favoured, with a ${pct(top.value)} chance of winning`;

  return (
    <article aria-labelledby="prediction-heading" className="space-y-8 animate-in fade-in duration-300">
      {/* ── Scoreboard ───────────────────────────────────────────────────── */}
      <div className="overflow-hidden rounded-lg border border-border bg-surface">
        <div className="px-5 pb-6 pt-5 sm:px-8">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="eyebrow">Prediction</p>
            {isAuthenticated ? (
              <Button size="sm" variant="outline" onClick={handleSave} loading={saving} disabled={saved}>
                {saved ? <Check className="text-win" aria-hidden="true" /> : !saving && <BookmarkPlus aria-hidden="true" />}
                {saved ? "Saved" : "Save"}
              </Button>
            ) : null}
          </div>

          <h2 id="prediction-heading" className="sr-only">
            Prediction for {home} against {away}
          </h2>

          {/* Phones: one row per team with its goals, like the overview's
              final. Three columns left each name too narrow to read. */}
          <div className="mt-4 divide-y divide-border rounded-md border border-border sm:hidden">
            {[
              { team: home, goals: result.predicted_home_score, fav: !close && top.key === "home" },
              { team: away, goals: result.predicted_away_score, fav: !close && top.key === "away" },
            ].map((row) => (
              <div key={row.team} className="flex items-center gap-3 px-4 py-3">
                <TeamFlag name={row.team} size="lg" className="shrink-0" />
                <span className="min-w-0 flex-1">
                  <span className="block font-display text-2xl font-bold uppercase leading-none tracking-wide text-foreground">{row.team}</span>
                  {row.fav && <span className="mt-1 block text-[11px] font-semibold uppercase tracking-wider text-primary">Favoured</span>}
                </span>
                <span className="scoreline text-4xl text-foreground" aria-label={`${row.goals} goals`}>{row.goals}</span>
              </div>
            ))}
            <p className="px-4 py-2 text-xs text-fg-muted">
              Most likely score
              {topScore ? <span className="tabular font-semibold text-foreground"> · {pct(topScore.probability)}</span> : null}
            </p>
          </div>

          <div className="mt-5 hidden grid-cols-[1fr_auto_1fr] items-center gap-3 sm:grid sm:gap-8">
            <ScoreSide team={home} align="right" favoured={!close && top.key === "home"} />
            <div className="text-center">
              <p className="scoreline text-6xl text-foreground sm:text-7xl" aria-label={`Most likely score ${result.predicted_home_score} to ${result.predicted_away_score}`}>
                {result.predicted_home_score}
                <span className="mx-2 text-fg-subtle sm:mx-3" aria-hidden="true">
                  –
                </span>
                {result.predicted_away_score}
              </p>
              <p className="mt-2 text-xs text-fg-muted">
                Most likely score
                {topScore ? <span className="tabular font-semibold text-foreground"> · {pct(topScore.probability)}</span> : null}
              </p>
            </div>
            <ScoreSide team={away} align="left" favoured={!close && top.key === "away"} />
          </div>

          <p className="mt-6 text-center text-base font-semibold text-foreground sm:text-lg">{headline}</p>
        </div>

        {/* Three outcomes on one bar. Each segment carries its own text label
            and percentage, so the split never depends on telling colours apart. */}
        <div className="border-t border-border px-5 py-5 sm:px-8">
          <div
            role="img"
            aria-label={`${home} win ${pct(pHome)}, draw ${pct(pDraw)}, ${away} win ${pct(pAway)}`}
            className="flex h-3 w-full overflow-hidden rounded-full bg-surface-3"
          >
            <span className="h-full bg-primary" style={{ width: `${pHome * 100}%` }} />
            <span className="h-full border-x-2 border-surface bg-draw" style={{ width: `${pDraw * 100}%` }} />
            <span className="h-full bg-foreground/80" style={{ width: `${pAway * 100}%` }} />
          </div>
          <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
            <OutcomeFigure swatch="bg-primary" label={`${home} win`} value={pHome} lead={top.key === "home"} align="left" />
            <OutcomeFigure swatch="bg-draw" label="Draw" value={pDraw} lead={top.key === "draw"} align="center" />
            <OutcomeFigure swatch="bg-foreground/80" label={`${away} win`} value={pAway} lead={top.key === "away"} align="right" />
          </dl>
        </div>

        <dl className="grid grid-cols-2 divide-x divide-border border-t border-border text-center">
          <div className="px-4 py-3">
            <dt className="eyebrow">{home} expected goals</dt>
            <dd className="scoreline mt-1 text-2xl text-foreground">{formatGoals(result.expected_home_goals)}</dd>
          </div>
          <div className="px-4 py-3">
            <dt className="eyebrow">{away} expected goals</dt>
            <dd className="scoreline mt-1 text-2xl text-foreground">{formatGoals(result.expected_away_goals)}</dd>
          </div>
        </dl>

        <p className="border-t border-border bg-surface-2 px-5 py-3 text-xs leading-relaxed text-fg-muted sm:px-8">
          <Info className="mr-1.5 inline h-3.5 w-3.5 -translate-y-px text-fg-subtle" aria-hidden="true" />
          These are probabilities, not a forecast of what will happen.
          {topScore
            ? ` Even the most likely score comes up only about ${Math.round(topScore.probability * 100)} times in 100; the result and the exact score are separate questions.`
            : " The result and the exact score are separate questions."}
        </p>
      </div>

      {/* ── Detail ───────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
        {result.top_scorelines.length > 0 && (
          <ScorelineDistribution scorelines={result.top_scorelines} mostLikelyScore={result.most_likely_score} />
        )}
        {result.prediction_explanation && <ShapExplanation explanation={result.prediction_explanation} />}
        {result.head_to_head && <HeadToHeadCard stats={result.head_to_head} homeTeam={home} awayTeam={away} />}

        {result.insights && result.insights.length > 0 && (
          <section aria-labelledby="factors-heading" className="space-y-3">
            <SectionHeader id="factors-heading" title="From the record" as="h3" />
            {/* Rule-based observations from real match history; each appears
                only when its threshold is met. */}
            <ul className="divide-y divide-border">
              {result.insights.map((insight, i) => {
                const Icon = INSIGHT_ICON[insight.type];
                return (
                  <li key={i} className="flex items-start gap-3 py-3">
                    <Icon
                      className={cn("mt-0.5 h-4 w-4 shrink-0", insight.type === "warning" ? "text-warning" : "text-primary")}
                      aria-hidden="true"
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-foreground">{insight.title}</p>
                      <p className="mt-0.5 text-sm leading-relaxed text-fg-muted">{insight.description}</p>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </div>

      <p className="text-center text-xs text-fg-subtle">
        Model <span className="font-code">{result.model_version}</span>
        <span className="mx-1.5" aria-hidden="true">
          ·
        </span>
        Reference <span className="font-code">{result.prediction_id.slice(0, 8)}</span>
      </p>
    </article>
  );
}

function ScoreSide({ team, align, favoured }: { team: string; align: "left" | "right"; favoured: boolean }) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-2", align === "right" ? "items-end text-right" : "items-start text-left")}>
      <TeamFlag name={team} size="xl" />
      <p className="max-w-full break-normal font-display text-2xl font-bold uppercase leading-none tracking-wide text-foreground sm:text-3xl lg:text-4xl">
        {team}
      </p>
      {/* Reserved line: keeps both sides the same height whether or not one is favoured. */}
      <p className="h-4 text-[11px] font-semibold uppercase tracking-wider text-primary">{favoured ? "Favoured" : ""}</p>
    </div>
  );
}

function OutcomeFigure({
  swatch,
  label,
  value,
  lead,
  align,
}: {
  swatch: string;
  label: string;
  value: number;
  lead: boolean;
  align: "left" | "center" | "right";
}) {
  return (
    <div className={cn("min-w-0", align === "left" && "text-left", align === "right" && "text-right")}>
      <dt
        className={cn(
          "flex items-center gap-1.5 text-xs text-fg-muted",
          align === "center" && "justify-center",
          align === "right" && "justify-end"
        )}
      >
        <span className={cn("h-2 w-2 shrink-0 rounded-sm", swatch)} aria-hidden="true" />
        <span className="truncate">{label}</span>
      </dt>
      <dd className={cn("scoreline mt-1 text-2xl sm:text-3xl", lead ? "text-foreground" : "text-fg-muted")}>{pct(value)}</dd>
    </div>
  );
}
