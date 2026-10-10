"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { CalendarDays } from "lucide-react";
import { tournamentApi } from "@/lib/api/tournament";
import { wc2026Api } from "@/lib/api/wc2026";
import { getApiErrorMessage } from "@/lib/api/client";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { ListSkeleton } from "@/components/ui/page-skeletons";
import { TeamFlag } from "@/components/football/team-flag";
import { cn } from "@/lib/utils";
import { formatMatchDate, scoreQualifier, sideScores, stageLabel } from "@/lib/wc2026";
import type { BracketNodeData, WcStage } from "@/types";

/** A schedule slot that is still a placeholder ("W53") rather than a team code. */
const isCode = (value: string) => value.length === 3;

/**
 * All 104 matches in date order, with the result where one exists.
 *
 * The schedule endpoint only knows the fixture list, so on its own this table
 * showed a finished tournament as 104 upcoming fixtures with no scores. Results
 * are joined in from the bracket endpoint by match number. If that request
 * fails the schedule still renders, and says the results are unavailable
 * rather than implying the matches have not been played.
 */
export function ScheduleView() {
  const { data: schedule, error, isLoading, mutate } = useSWR("tournament-schedule", () => tournamentApi.getSchedule());
  const { data: bracket, error: resultsError } = useSWR("wc2026-bracket", wc2026Api.getBracket);
  const [stageFilter, setStageFilter] = useState("all");

  const matches = useMemo(() => schedule?.matches ?? [], [schedule]);
  const results = useMemo(() => {
    const map = new Map<number, BracketNodeData>();
    for (const node of bracket?.nodes ?? []) map.set(node.match_number, node);
    return map;
  }, [bracket]);

  const stages = useMemo(() => Array.from(new Set(matches.map((m) => m.stage))), [matches]);
  const filtered = useMemo(
    () => (stageFilter === "all" ? matches : matches.filter((m) => m.stage === stageFilter)),
    [matches, stageFilter]
  );
  const played = filtered.filter((m) => results.get(m.match_number)?.status === "completed").length;

  if (isLoading) return <ListSkeleton count={10} />;

  if (error) {
    return <ErrorState title="Couldn't load the schedule" description={getApiErrorMessage(error)} onRetry={() => mutate()} />;
  }

  if (matches.length === 0) {
    return <EmptyState icon={CalendarDays} title="No schedule is available" />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Select value={stageFilter} onValueChange={setStageFilter}>
          <SelectTrigger className="h-11 w-56" aria-label="Filter by stage">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All stages</SelectItem>
            {stages.map((stage) => (
              <SelectItem key={stage} value={stage}>
                {stageLabel(stage as WcStage)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p role="status" aria-live="polite" className="text-sm text-fg-muted">
          {filtered.length} {filtered.length === 1 ? "match" : "matches"}
          {bracket ? `, ${played} played` : ""}
        </p>
      </div>

      {resultsError && (
        <p role="status" className="rounded-md border border-border bg-surface px-4 py-2.5 text-sm text-fg-muted">
          Results could not be loaded, so only the fixture list is shown.
        </p>
      )}

      <div
        className="overflow-x-auto rounded-lg border border-border"
        tabIndex={0}
        role="region"
        aria-label="Match schedule table"
      >
        <table className="w-full min-w-[38rem] text-sm">
          <caption className="sr-only">World Cup 2026 matches with date, teams, score, stage and host city</caption>
          <thead className="border-b border-border bg-surface-2">
            <tr>
              <th scope="col" className="eyebrow w-32 py-2.5 pl-4 pr-2 text-left">Date (ET)</th>
              <th scope="col" className="eyebrow px-2 py-2.5 text-center">Match</th>
              <th scope="col" className="eyebrow w-36 px-2 py-2.5 text-left">Stage</th>
              <th scope="col" className="eyebrow hidden w-48 py-2.5 pl-2 pr-4 text-left lg:table-cell">Host city</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filtered.map((m) => {
              const node = results.get(m.match_number);
              const done = node?.status === "completed";
              const scores = node ? sideScores(node) : null;
              const qualifier = node ? scoreQualifier(node) : null;
              // Prefer the bracket's team names; fall back to the schedule's code.
              const home = node?.home_team ?? m.home_team;
              const away = node?.away_team ?? m.away_team;
              const homeWon = done && node?.winner_team === node?.home_team;
              const awayWon = done && node?.winner_team === node?.away_team;
              return (
                <tr key={m.match_number} className="bg-surface">
                  <td className="whitespace-nowrap py-2.5 pl-4 pr-2 text-fg-muted">
                    <span className="font-semibold text-foreground">{formatMatchDate(m.date) ?? m.date}</span>
                    <span className="ml-2 text-xs">{m.kickoff_time_et}</span>
                  </td>
                  <td className="px-2 py-2.5">
                    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 sm:gap-3">
                      <span className={cn("flex min-w-0 items-center justify-end gap-2", homeWon ? "font-semibold text-foreground" : "text-fg-muted")}>
                        <span className="text-right leading-tight">{home}</span>
                        <TeamFlag name={home} fifaCode={isCode(m.home_team) ? m.home_team : null} size="sm" />
                      </span>
                      <span className="min-w-[4.5rem] whitespace-nowrap text-center">
                        {done && scores ? (
                          <>
                            <span className="tabular font-semibold text-foreground">
                              {scores.home}–{scores.away}
                            </span>
                            {qualifier && <span className="ml-1 text-[10px] uppercase text-fg-subtle">{qualifier}</span>}
                          </>
                        ) : (
                          <span className="text-xs text-fg-subtle">{bracket ? "Not played" : "v"}</span>
                        )}
                      </span>
                      <span className={cn("flex min-w-0 items-center gap-2", awayWon ? "font-semibold text-foreground" : "text-fg-muted")}>
                        <TeamFlag name={away} fifaCode={isCode(m.away_team) ? m.away_team : null} size="sm" />
                        <span className="leading-tight">{away}</span>
                      </span>
                    </div>
                  </td>
                  <td className="px-2 py-2.5 text-fg-muted">{m.group ? `Group ${m.group}` : stageLabel(m.stage as WcStage)}</td>
                  <td className="hidden py-2.5 pl-2 pr-4 text-fg-muted lg:table-cell">{m.venue_city}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-fg-subtle">
        Kick-off times are Eastern Time, as published in the official schedule. Scores include extra time; a
        penalty shoot-out is shown beside the score.
      </p>
    </div>
  );
}
