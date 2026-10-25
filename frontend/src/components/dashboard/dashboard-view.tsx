"use client";

import useSWR from "swr";
import Link from "next/link";
import { ArrowRight, Check, Swords, Trophy, X } from "lucide-react";
import { analyticsApi } from "@/lib/api/analytics";
import { wc2026Api } from "@/lib/api/wc2026";
import { getApiErrorMessage } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { SectionHeader, Metric } from "@/components/ui/section";
import { TeamFlag } from "@/components/football/team-flag";
import { FootballPitchBackground } from "@/components/football/pitch-background";
import { useUser } from "@/hooks/use-user";
import { cn } from "@/lib/utils";
import { formatMatchDate, scoreQualifier, sideScores, stageLabel, predictionOutcome } from "@/lib/wc2026";
import type { BracketNodeData, GroupStanding } from "@/types";

/**
 * Overview.
 *
 * The 2026 World Cup has been played, so the page leads with what happened —
 * the final and the champion — and says so. Everything below is a reading of
 * the same finished tournament: how the last rounds went, who won each group,
 * and how the pre-tournament model scored against the real results.
 *
 * Every figure comes from an API response. The tournament blocks read the
 * file-backed WC2026 endpoints and the record counts read the database, so
 * each block has its own loading and error state: one unavailable source does
 * not blank the page.
 */
export function DashboardView() {
  const bracket = useSWR("wc2026-bracket", wc2026Api.getBracket);
  const standings = useSWR("wc2026-standings", wc2026Api.getStandings);
  const backtest = useSWR("wc2026-backtest", wc2026Api.getBacktest);
  const stats = useSWR("dashboard-stats", analyticsApi.getDashboardStats);
  const { isAuthenticated } = useUser();

  const nodes = bracket.data?.nodes ?? [];
  const final = nodes.find((n) => n.stage === "final") ?? null;
  const third = nodes.find((n) => n.stage === "third_place") ?? null;
  const semis = nodes.filter((n) => n.stage === "semi_final");
  const recent = stats.data?.recent_predictions ?? [];

  return (
    <div className="space-y-10">
      {/* ── The final ─────────────────────────────────────────────────────── */}
      {bracket.isLoading ? (
        <Skeleton className="h-72 w-full rounded-lg" />
      ) : bracket.error ? (
        <div className="rounded-lg border border-border bg-surface">
          <ErrorState
            title="Couldn't load the tournament"
            description={getApiErrorMessage(bracket.error)}
            onRetry={() => bracket.mutate()}
          />
        </div>
      ) : final ? (
        <FinalHero final={final} />
      ) : null}

      <div className="grid grid-cols-1 gap-10 lg:grid-cols-3">
        {/* ── Left: the tournament ────────────────────────────────────────── */}
        <div className="space-y-10 lg:col-span-2">
          {semis.length > 0 && (
            <section aria-labelledby="road-heading" className="space-y-3">
              <SectionHeader
                id="road-heading"
                title="Semi-finals"
                meta="Tick or cross: whether the pre-tournament model picked the winner"
                href="/tournaments"
                linkLabel="Full bracket"
              />
              <ul className="divide-y divide-border">
                {semis.map((node) => (
                  <ResultRow key={node.match_number} node={node} />
                ))}
                {third && <ResultRow node={third} />}
              </ul>
            </section>
          )}

          <section aria-labelledby="groups-heading" className="space-y-3">
            <SectionHeader
              id="groups-heading"
              title="Group winners"
              meta="Final tables, 12 groups"
              href="/tournaments?tab=standings"
              linkLabel="All standings"
            />
            {standings.isLoading ? (
              <Skeleton className="h-56 w-full rounded-lg" />
            ) : standings.error ? (
              <ErrorState
                title="Couldn't load the group tables"
                description={getApiErrorMessage(standings.error)}
                onRetry={() => standings.mutate()}
              />
            ) : (
              <GroupWinners groups={standings.data?.groups ?? []} />
            )}
          </section>
        </div>

        {/* ── Right: tools and the model's record ─────────────────────────── */}
        <div className="space-y-10">
          <section aria-labelledby="tools-heading" className="space-y-3">
            <SectionHeader id="tools-heading" title="Tools" />
            <div className="space-y-2">
              <ToolLink
                href="/predict"
                icon={Swords}
                title="Predict a match"
                description="Pick two teams for win, draw and loss chances, expected goals and likely scorelines."
              />
              <ToolLink
                href="/tournaments?tab=simulator"
                icon={Trophy}
                title="Simulate the tournament"
                description="Thousands of simulated World Cups from the pre-tournament ratings, or from the real group stage."
              />
            </div>
          </section>

          <section aria-labelledby="model-heading" className="space-y-3">
            <SectionHeader
              id="model-heading"
              title="Model vs reality"
              href="/tournaments?tab=backtest"
              linkLabel="Match by match"
            />
            {backtest.isLoading ? (
              <Skeleton className="h-48 w-full rounded-lg" />
            ) : backtest.error ? (
              <ErrorState
                title="Couldn't load the evaluation"
                description={getApiErrorMessage(backtest.error)}
                onRetry={() => backtest.mutate()}
              />
            ) : backtest.data ? (
              <div className="space-y-4">
                <dl className="grid grid-cols-2 gap-4">
                  <Metric
                    label="Winners called"
                    value={
                      backtest.data.accuracy !== null ? `${(backtest.data.accuracy * 100).toFixed(1)}%` : "—"
                    }
                    hint={`${backtest.data.correct} of ${backtest.data.n_matches_scored ?? "—"} matches`}
                  />
                  <Metric
                    label="Champion pick"
                    size="sm"
                    value={backtest.data.predicted_champion ?? "—"}
                    hint={
                      backtest.data.actual_champion
                        ? backtest.data.predicted_champion === backtest.data.actual_champion
                          ? "Correct"
                          : `Actual champion: ${backtest.data.actual_champion}`
                        : undefined
                    }
                  />
                </dl>
                <ul className="space-y-2" aria-label="Winners called correctly, by round">
                  {backtest.data.by_stage.map((s) => (
                    <li key={s.stage} className="grid grid-cols-[7.5rem_1fr_2.75rem] items-center gap-3 text-xs">
                      <span className="truncate text-fg-muted">{stageLabel(s.stage)}</span>
                      <span className="h-1.5 overflow-hidden rounded-full bg-surface-3" aria-hidden="true">
                        <span
                          className="block h-full rounded-full bg-primary"
                          style={{ width: `${Math.round(s.accuracy * 100)}%` }}
                        />
                      </span>
                      <span className="tabular text-right font-semibold text-foreground">
                        {s.correct}/{s.total}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="text-xs leading-relaxed text-fg-subtle">
                  A historical evaluation of {backtest.data.model_version ?? "the frozen model"}: its
                  predictions were fixed before these results were compared with them. One tournament
                  is a small sample.
                </p>
              </div>
            ) : null}
          </section>

          <section aria-labelledby="record-heading" className="space-y-3">
            <SectionHeader id="record-heading" title="On record" />
            {stats.isLoading ? (
              <Skeleton className="h-20 w-full rounded-lg" />
            ) : stats.error ? (
              // The database is a separate source from the tournament files;
              // if it is down, say so here and leave the rest of the page up.
              <p role="status" className="rounded-lg border border-border bg-surface px-4 py-3 text-sm text-fg-muted">
                Match and team counts are unavailable right now.{" "}
                <button
                  type="button"
                  onClick={() => stats.mutate()}
                  className="font-semibold text-primary underline-offset-2 hover:underline"
                >
                  Retry
                </button>
              </p>
            ) : stats.data ? (
              <dl className="grid grid-cols-2 gap-4">
                <Metric label="Matches" value={stats.data.total_matches_analyzed.toLocaleString()} size="sm" />
                <Metric
                  label="Teams in the record"
                  value={stats.data.total_teams.toLocaleString()}
                  size="sm"
                  hint="Every side in the match record, including historical and regional teams. 48 played in 2026."
                />
                {isAuthenticated && (
                  <Metric
                    label="Your saved predictions"
                    value={stats.data.total_predictions.toLocaleString()}
                    size="sm"
                  />
                )}
              </dl>
            ) : null}

            {isAuthenticated && recent.length > 0 && (
              <div className="pt-2">
                <h3 className="eyebrow mb-2">Your recent predictions</h3>
                <ul className="divide-y divide-border">
                  {recent.map((p) => (
                    <li key={p.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                      <span className="flex min-w-0 items-center gap-2">
                        <TeamFlag name={p.home_team} size="xs" />
                        <span className="truncate">{p.home_team}</span>
                        <span className="text-fg-subtle">v</span>
                        <TeamFlag name={p.away_team} size="xs" />
                        <span className="truncate">{p.away_team}</span>
                      </span>
                      <span className="tabular shrink-0 font-semibold text-foreground">
                        {p.predicted_home_score}–{p.predicted_away_score}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

/* ── The final: the page's single focal point ─────────────────────────────── */

export function FinalHero({ final }: { final: BracketNodeData }) {
  const scores = sideScores(final);
  const qualifier = scoreQualifier(final);
  const champion = final.winner_team;
  const date = formatMatchDate(final.date);
  const year = final.date?.slice(0, 4);

  return (
    <section
      aria-labelledby="final-heading"
      className="relative isolate overflow-hidden rounded-xl border border-black/20 text-white shadow-[0_18px_40px_-20px_rgba(6,40,18,0.65)]"
    >
      <FootballPitchBackground />

      <div className="relative px-5 py-6 sm:px-8 sm:py-8 lg:px-12">
        <div className="flex flex-wrap items-center justify-between gap-2">
          {/* On a phone the date drops to its own line instead of breaking mid-phrase. */}
          <p className="text-[11px] font-semibold uppercase leading-snug tracking-[0.12em] text-white/90 sm:text-xs sm:tracking-[0.14em]">
            <span className="block sm:inline">FIFA World Cup 2026 · Final</span>
            {date && (
              <>
                <span className="hidden sm:inline"> · </span>
                <span className="block sm:inline">{`${date}${year ? ` ${year}` : ""}`}</span>
              </>
            )}
          </p>
          <span className="inline-flex shrink-0 items-center rounded-md bg-white/85 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-800 sm:px-2.5 sm:text-[11px]">
            Tournament complete
          </span>
        </div>

        <h2 id="final-heading" className="sr-only">
          World Cup final: {final.home_team} {scores.home}, {final.away_team} {scores.away}
          {qualifier ? ` (${qualifier})` : ""}
        </h2>

        {/* Phones: one row per team, name left and goals right, the way a live score is read on a handset. */}
        <div className="mt-5 divide-y divide-white/15 rounded-md border border-white/20 bg-[#0b2d16]/90 shadow-[0_6px_18px_-8px_rgba(0,0,0,0.6)] sm:hidden" aria-hidden="true">
          {[
            { team: final.home_team, goals: scores.home },
            { team: final.away_team, goals: scores.away },
          ].map((row, i) => (
            <div key={i} className="flex items-center gap-3 px-4 py-3">
              {row.team && <TeamFlag name={row.team} size="lg" className="shrink-0" />}
              <span
                className={cn(
                  "min-w-0 flex-1 font-display text-2xl font-bold uppercase leading-none tracking-wide",
                  champion === row.team ? "text-white" : "text-white/75"
                )}
              >
                {row.team}
                {champion === row.team && (
                  <span className="ml-2 inline-flex items-center gap-1 align-middle font-sans text-[11px] font-semibold tracking-wider text-sky-200">
                    <Trophy className="h-3.5 w-3.5" />
                    Champions
                  </span>
                )}
              </span>
              <span className="scoreline text-4xl text-white">{row.goals ?? "–"}</span>
            </div>
          ))}
          {qualifier && (
            <p className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-white/80">
              {qualifier === "aet" ? "After extra time" : qualifier}
            </p>
          )}
        </div>

        <div className="mt-8 hidden grid-cols-[1fr_auto_1fr] items-start gap-3 sm:grid sm:gap-8" aria-hidden="true">
          <FinalSide team={final.home_team} winner={champion === final.home_team} align="right" />
          <div className="self-center text-center">
            <p className="scoreline text-6xl text-white drop-shadow-[0_2px_8px_rgba(0,0,0,0.45)] sm:text-8xl">
              {scores.home ?? "–"}
              <span className="mx-2 text-white/70 sm:mx-4">–</span>
              {scores.away ?? "–"}
            </p>
            {qualifier && (
              <p className="mt-2 text-xs font-semibold uppercase tracking-[0.14em] text-white/85">
                {qualifier === "aet" ? "After extra time" : qualifier}
              </p>
            )}
          </div>
          <FinalSide team={final.away_team} winner={champion === final.away_team} align="left" />
        </div>

        <div className="mt-8 flex flex-wrap items-center justify-between gap-x-8 gap-y-3 border-t border-white/25 pt-4 text-sm">
          <p className="text-white/90">{final.venue}</p>
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm">
              <Link href="/tournaments">
                View the bracket
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
            <Button
              asChild
              size="sm"
              variant="outline"
              className="border-transparent bg-white text-slate-900 hover:bg-white/90 hover:text-slate-900"
            >
              <Link href="/predict">Predict a match</Link>
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

function FinalSide({ team, winner, align }: { team: string | null; winner: boolean; align: "left" | "right" }) {
  if (!team) return <div />;
  return (
    <div className={cn("flex min-w-0 flex-col gap-2", align === "right" ? "items-end text-right" : "items-start text-left")}>
      <TeamFlag name={team} size="xl" className="shadow-md" />
      <p
        className={cn(
          // Wraps only at spaces ("Bosnia and Herzegovina"); a single word is never split.
          "max-w-full break-normal font-display text-2xl font-bold uppercase leading-none tracking-wide drop-shadow-[0_1px_4px_rgba(0,0,0,0.5)] sm:text-3xl lg:text-4xl",
          winner ? "text-white" : "text-white/85"
        )}
      >
        {team}
      </p>
      {winner ? (
        <p className="inline-flex h-4 items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-sky-200">
          <Trophy className="h-3.5 w-3.5" />
          Champions
        </p>
      ) : (
        <span className="h-4" aria-hidden="true" />
      )}
    </div>
  );
}

/* ── A completed knockout tie, one line ───────────────────────────────────── */

function ResultRow({ node }: { node: BracketNodeData }) {
  const scores = sideScores(node);
  const qualifier = scoreQualifier(node);
  const outcome = predictionOutcome(node);
  const homeWon = node.winner_team === node.home_team;
  const awayWon = node.winner_team === node.away_team;

  return (
    <li className="grid grid-cols-[1fr_auto_1fr_1.25rem] items-center gap-x-2 gap-y-1 py-2.5 text-sm sm:grid-cols-[7rem_1fr_auto_1fr_1.25rem] sm:gap-3">
      <span className="col-span-full text-xs text-fg-subtle sm:col-auto sm:truncate">{stageLabel(node.stage)}</span>
      <span className={cn("flex min-w-0 items-center justify-end gap-2", homeWon ? "font-semibold text-foreground" : "text-fg-muted")}>
        {/* Names wrap at spaces instead of truncating. */}
        <span className="text-right leading-tight">{node.home_team}</span>
        {node.home_team && <TeamFlag name={node.home_team} size="sm" />}
      </span>
      <span className="tabular whitespace-nowrap text-center font-semibold text-foreground">
        {scores.home}–{scores.away}
        {qualifier && <span className="ml-1 text-[10px] font-medium uppercase text-fg-subtle">{qualifier}</span>}
      </span>
      <span className={cn("flex min-w-0 items-center gap-2", awayWon ? "font-semibold text-foreground" : "text-fg-muted")}>
        {node.away_team && <TeamFlag name={node.away_team} size="sm" />}
        <span className="leading-tight">{node.away_team}</span>
      </span>
      {outcome === null ? (
        <span />
      ) : outcome ? (
        <Check className="h-4 w-4 text-win" role="img" aria-label="Model picked the winner" />
      ) : (
        <X className="h-4 w-4 text-loss" role="img" aria-label="Model picked the other side" />
      )}
    </li>
  );
}

/* ── Twelve groups, winner and runner-up ──────────────────────────────────── */

function GroupWinners({ groups }: { groups: GroupStanding[] }) {
  if (groups.length === 0) {
    return <p className="py-6 text-sm text-fg-muted">No group tables are available.</p>;
  }
  return (
    <table className="w-full table-fixed text-sm">
      <caption className="sr-only">Winner and runner-up of each World Cup 2026 group, with points</caption>
      <thead>
        <tr className="text-left">
          <th scope="col" className="eyebrow w-12 py-2 pr-1 font-semibold sm:w-14">
              <abbr title="Group" className="no-underline sm:hidden">Grp</abbr>
              <span className="hidden sm:inline">Group</span>
            </th>
          <th scope="col" className="eyebrow py-2 pr-2 font-semibold">Winner</th>
          <th scope="col" className="eyebrow py-2 pl-2 font-semibold">Runner-up</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border border-t border-border">
        {groups.map((g) => {
          const rows = [...g.standings].sort((a, b) => a.position - b.position);
          const [first, second] = rows;
          return (
            <tr key={g.group}>
              <th scope="row" className="py-2 text-left font-display text-lg font-semibold text-fg-muted">
                {g.group}
              </th>
              <td className="py-2 pr-2 align-top">
                {first && <TeamPoints name={first.team} points={first.points} strong />}
              </td>
              <td className="py-2 pl-2 align-top">
                {second && <TeamPoints name={second.team} points={second.points} />}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** Flag, name (wraps at spaces, never truncated) and points, in one cell. */
function TeamPoints({ name, points, strong = false }: { name: string; points: number; strong?: boolean }) {
  return (
    <span className="flex items-start gap-2">
      <TeamFlag name={name} size="sm" className="mt-0.5" />
      <span className={cn("min-w-0 flex-1 leading-tight", strong ? "font-semibold text-foreground" : "text-fg-muted")}>{name}</span>
      <span className={cn("tabular shrink-0", strong ? "font-semibold text-foreground" : "text-fg-muted")}>
        {points}
        <span className="sr-only"> points</span>
      </span>
    </span>
  );
}

function ToolLink({
  href,
  icon: Icon,
  title,
  description,
}: {
  href: string;
  icon: typeof Trophy;
  title: string;
  description: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-start gap-3 rounded-lg border border-border bg-surface p-4 transition-colors hover:border-border-strong hover:bg-surface-2"
    >
      <Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-foreground">{title}</span>
        <span className="mt-0.5 block text-xs leading-relaxed text-fg-muted">{description}</span>
      </span>
      <ArrowRight
        className="mt-0.5 h-4 w-4 shrink-0 text-fg-subtle transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
        aria-hidden="true"
      />
    </Link>
  );
}
