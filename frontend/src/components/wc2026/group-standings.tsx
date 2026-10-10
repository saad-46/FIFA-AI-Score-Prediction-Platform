"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useBracket, useStandings, useWc2026Teams } from "@/hooks/use-wc2026";
import { getApiErrorMessage } from "@/lib/api/client";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { TeamFlag } from "@/components/football/team-flag";
import type { GroupStanding, StandingRow, Wc2026TeamMeta } from "@/types";

/**
 * Final group tables A–L.
 *
 * WC2026 sends the top two of each group plus the eight best third-placed
 * teams to the Round of 32, so qualification cannot be read from a group table
 * alone. Rather than guess, the R32 field is derived from the bracket itself —
 * a team is marked qualified because it actually appears in a Round-of-32
 * fixture, not because of an assumed cut-off rule.
 */
export function GroupStandings() {
  const { data, error, isLoading, mutate } = useStandings();
  const { data: bracket } = useBracket();
  const { data: teamsData } = useWc2026Teams();
  const reduceMotion = useReducedMotion();

  const qualified = new Set<string>();
  for (const node of bracket?.nodes ?? []) {
    if (node.stage !== "round_of_32") continue;
    if (node.home_team) qualified.add(node.home_team);
    if (node.away_team) qualified.add(node.away_team);
  }

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-56 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        title="Couldn't load the group tables"
        description={getApiErrorMessage(error)}
        onRetry={() => mutate()}
      />
    );
  }

  const groups = data?.groups ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 font-mono text-[10px] uppercase tracking-wider text-fg-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-0.5 rounded-full bg-primary" aria-hidden="true" />
          Advanced to Round of 32
        </span>
        <span>P played · W won · D drawn · L lost · GD goal difference · Pts points</span>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {groups.map((group, index) => (
          <motion.div
            key={group.group}
            initial={reduceMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: "easeOut", delay: reduceMotion ? 0 : index * 0.03 }}
          >
            <GroupTable group={group} qualified={qualified} teams={teamsData?.teams} />
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function GroupTable({
  group,
  qualified,
  teams,
}: {
  group: GroupStanding;
  qualified: Set<string>;
  teams?: Record<string, Wc2026TeamMeta>;
}) {
  return (
    <section className="overflow-hidden rounded-lg border border-border bg-surface">
      <header className="border-b border-border bg-surface-2 px-3 py-2">
        <h2 className="font-display text-lg font-semibold uppercase leading-none tracking-wide text-foreground">
          Group {group.group}
        </h2>
      </header>

      {/* A scrollable region needs to be reachable from the keyboard, and a name
          so a screen reader says what it is. */}
      <div
        className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
        tabIndex={0}
        role="region"
        aria-label={`Group ${group.group} standings table`}
      >
        <table className="w-full text-sm">
          <caption className="sr-only">Group {group.group} final standings</caption>
          <thead>
            <tr className="eyebrow border-b border-border">
              {/* w-full + max-w-0: the name column takes whatever the number
                  columns leave and truncates inside it. With max-w-0 alone it
                  collapsed to a few characters -- "Sou..." for both South
                  Africa and South Korea in the same group. */}
              <th scope="col" className="w-full max-w-0 px-3 py-1.5 text-left font-semibold">
                Team
              </th>
              <th scope="col" className="px-1 py-1.5 text-right font-semibold">P</th>
              <th scope="col" className="px-1 py-1.5 text-right font-semibold">W</th>
              <th scope="col" className="px-1 py-1.5 text-right font-semibold">D</th>
              <th scope="col" className="px-1 py-1.5 text-right font-semibold">L</th>
              {/* GD is the least-scannable column and the first to give up its
                  width so team names stay readable on a 390px screen. */}
              <th scope="col" className="hidden px-1 py-1.5 text-right font-normal sm:table-cell">
                GD
              </th>
              <th scope="col" className="px-3 py-1.5 text-right font-semibold">Pts</th>
            </tr>
          </thead>
          <tbody>
            {group.standings.map((row) => (
              <StandingTableRow
                key={row.team}
                row={row}
                qualified={qualified.has(row.team)}
                code={teams?.[row.team]?.fifa_code ?? null}
              />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StandingTableRow({
  row,
  qualified,
  code,
}: {
  row: StandingRow;
  qualified: boolean;
  code: string | null;
}) {
  return (
    <tr className="border-b border-border/40 last:border-0 transition-colors hover:bg-surface-2/50">
      <th scope="row" className="w-full max-w-0 px-3 py-2 text-left font-normal">
        <span className="flex items-center gap-2">
          {/* Qualification is encoded by the rail *and* the position number and
              an sr-only word — never by colour alone. */}
          <span
            aria-hidden="true"
            className={cn(
              "h-4 w-0.5 shrink-0 rounded-full",
              qualified ? "bg-primary" : "bg-transparent"
            )}
          />
          <span className="tabular w-3 shrink-0 text-xs text-fg-subtle">{row.position}</span>
          <TeamFlag name={row.team} fifaCode={code} size="sm" />
          <span className={cn("leading-tight", qualified ? "font-semibold text-foreground" : "text-fg-muted")}>{row.team}</span>
          {qualified && <span className="sr-only">— advanced to the Round of 32</span>}
        </span>
      </th>
      <Cell value={row.played} />
      <Cell value={row.won} />
      <Cell value={row.drawn} />
      <Cell value={row.lost} />
      <Cell
        value={row.goal_difference > 0 ? `+${row.goal_difference}` : row.goal_difference}
        className="hidden sm:table-cell"
      />
      <td className="tabular px-3 py-2 text-right text-sm font-bold text-foreground">
        {row.points}
      </td>
    </tr>
  );
}

function Cell({ value, className }: { value: number | string; className?: string }) {
  return (
    <td
      className={cn(
        "tabular px-1.5 py-2 text-right text-xs text-fg-muted",
        className
      )}
    >
      {value}
    </td>
  );
}
