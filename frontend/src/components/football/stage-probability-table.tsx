"use client";

import { useMemo, useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TeamIdentity } from "@/components/football/team-identity";
import { cn } from "@/lib/utils";
import type { TeamTournamentProbabilities } from "@/types";

interface StageProbabilityTableProps {
  probabilities: Record<string, TeamTournamentProbabilities>;
  /** fifa_code -> full team name, for display. Falls back to the code. */
  teamNames?: Record<string, string>;
}

type StageKey = keyof TeamTournamentProbabilities;

const STAGES: { key: StageKey; label: string }[] = [
  { key: "group", label: "Group" },
  { key: "r32", label: "R32" },
  { key: "r16", label: "R16" },
  { key: "qf", label: "QF" },
  { key: "sf", label: "SF" },
  { key: "third_place", label: "3rd" },
  { key: "final", label: "Final" },
  { key: "winner", label: "Winner" },
];

function heatBackground(value: number) {
  const pct = Math.min(Math.max(value, 0), 1) * 35;
  // color-mix keeps this theme-aware (uses the live --win token) instead of
  // a fixed dark-mode-only rgba() literal.
  return `color-mix(in srgb, var(--win) ${pct}%, transparent)`;
}

/** The core tournament-simulation deliverable: all 48 teams × 8 cumulative
 * stage-reached probabilities, sortable by column, heat-shaded. Scrolls
 * horizontally within its own container on narrow screens. */
export function StageProbabilityTable({ probabilities, teamNames }: StageProbabilityTableProps) {
  const [sortKey, setSortKey] = useState<StageKey>("winner");

  const rows = useMemo(() => {
    return Object.entries(probabilities)
      .map(([code, probs]) => ({ code, name: teamNames?.[code] ?? code, ...probs }))
      .sort((a, b) => b[sortKey] - a[sortKey]);
  }, [probabilities, teamNames, sortKey]);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Team</TableHead>
          {STAGES.map((s) => (
            <TableHead
              key={s.key}
              className="p-0 text-center"
              aria-sort={sortKey === s.key ? "descending" : "none"}
            >
              <button
                type="button"
                onClick={() => setSortKey(s.key)}
                className={cn(
                  "h-10 w-full px-2 text-center font-medium transition-colors hover:text-foreground",
                  sortKey === s.key && "text-primary"
                )}
              >
                {s.label}
              </button>
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.code}>
            <TableCell>
              <TeamIdentity name={row.name} fifaCode={row.code} size="sm" />
            </TableCell>
            {STAGES.map((s) => (
              <TableCell
                key={s.key}
                className="text-center font-mono"
                style={{ backgroundColor: heatBackground(row[s.key]) }}
              >
                {(row[s.key] * 100).toFixed(1)}%
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
