"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { ArrowDown, ArrowUp, ChevronRight, Search } from "lucide-react";
import { teamsApi } from "@/lib/api/teams";
import { getApiErrorMessage } from "@/lib/api/client";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { TeamFlag } from "@/components/football/team-flag";
import { cn } from "@/lib/utils";
import type { Team } from "@/types";

type SortKey = "name" | "group" | "rank" | "elo";
type SortDir = "asc" | "desc";

const collator = new Intl.Collator("en", { sensitivity: "base" });

/** Nulls always sort last, whichever direction is active. */
function compare(a: Team, b: Team, key: SortKey, dir: SortDir): number {
  const sign = dir === "asc" ? 1 : -1;
  const byName = collator.compare(a.name, b.name);
  if (key === "name") return sign * byName;
  if (key === "group") {
    const d = collator.compare(a.wc2026_group ?? "~", b.wc2026_group ?? "~");
    return d !== 0 ? sign * d : byName;
  }
  const av = key === "rank" ? a.fifa_ranking : a.elo_rating;
  const bv = key === "rank" ? b.fifa_ranking : b.elo_rating;
  if (av == null && bv == null) return byName;
  if (av == null) return 1;
  if (bv == null) return -1;
  return av !== bv ? sign * (av - bv) : byName;
}

/**
 * The World Cup 2026 team directory: all 48 teams in one sortable table.
 *
 * It used to be 48 identical cards in a three-column grid, each repeating the
 * same two labels ("FIFA rank", "Elo") around two numbers. A table states those
 * labels once, fits four times as many teams on a screen, and lets the reader
 * do the one thing a directory of ranked teams invites: sort it.
 *
 * Reads `/teams/wc2026`, which is scoped to the 48 qualifiers server-side.
 * Search and the group filter work on the loaded list in memory rather than
 * calling `/teams/search`: that endpoint covers all 335 rows in the teams
 * table, including non-national entities this page must not surface.
 *
 * Rank and Elo are whatever the API returns; a missing value is shown as a
 * dash, never filled in.
 */
export function TeamsView() {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState<string>("all");
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: "name", dir: "asc" });

  const { data, error, isLoading, mutate } = useSWR("wc2026-team-directory", teamsApi.getWc2026Teams, {
    revalidateOnFocus: false,
  });

  const groups = useMemo(
    () => [...new Set((data ?? []).map((t) => t.wc2026_group).filter((g): g is string => Boolean(g)))].sort(),
    [data]
  );

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data ?? [])
      .filter((t) => group === "all" || t.wc2026_group === group)
      // Name or FIFA code, so both "Brazil" and "BRA" find Brazil.
      .filter((t) => !q || t.name.toLowerCase().includes(q) || (t.fifa_code ?? "").toLowerCase().includes(q))
      .sort((a, b) => compare(a, b, sort.key, sort.dir));
  }, [data, query, group, sort]);

  const toggleSort = (key: SortKey) =>
    setSort((s) =>
      s.key === key
        ? { key, dir: s.dir === "asc" ? "desc" : "asc" }
        // First click sorts the way people read each column: A–Z, best rank
        // first (lowest number), highest Elo first.
        : { key, dir: key === "elo" ? "desc" : "asc" }
    );

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative w-full lg:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" aria-hidden="true" />
          <Input
            type="search"
            placeholder="Search by team or code"
            className="h-11 pl-9"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search teams by name or FIFA code"
          />
        </div>

        {groups.length > 0 && (
          <div role="group" aria-label="Filter by group" className="-mx-4 flex gap-1 overflow-x-auto px-4 pb-1 lg:mx-0 lg:px-0 lg:pb-0">
            <GroupChip label="All" active={group === "all"} onClick={() => setGroup("all")} />
            {groups.map((g) => (
              <GroupChip key={g} label={g} spoken={`Group ${g}`} active={group === g} onClick={() => setGroup(g)} />
            ))}
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-px overflow-hidden rounded-lg border border-border" aria-busy="true" aria-label="Loading teams">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 bg-surface px-4 py-3">
              <Skeleton className="h-5 w-7" />
              <Skeleton className="h-4 w-40" />
              <Skeleton className="ml-auto h-4 w-24" />
            </div>
          ))}
        </div>
      ) : error ? (
        <ErrorState title="Couldn't load the teams" description={getApiErrorMessage(error)} onRetry={() => mutate()} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No teams found"
          description={query ? `No 2026 team matches "${query}"${group !== "all" ? ` in Group ${group}` : ""}.` : "No teams in this group."}
        />
      ) : (
        // overflow-x-auto, not hidden: at narrow widths the columns are sized to
        // fit, but if a long name or a large text size ever pushes the table
        // wider, the region scrolls instead of silently clipping a column.
        <div className="relative overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <caption className="sr-only">
              World Cup 2026 teams with group, confederation, pre-tournament FIFA ranking and Elo rating. Column
              headers sort the table.
            </caption>
            <thead className="border-b border-border bg-surface-2">
              <tr>
                <SortHeader label="Team" sortKey="name" sort={sort} onSort={toggleSort} className="pl-3 text-left sm:pl-4" />
                <SortHeader label="Group" short="Grp" sortKey="group" sort={sort} onSort={toggleSort} className="w-16 text-left sm:w-20" />
                <th scope="col" className="eyebrow hidden px-2 py-2.5 text-left md:table-cell">
                  Confederation
                </th>
                <SortHeader label="FIFA rank" short="Rank" sortKey="rank" sort={sort} onSort={toggleSort} className="w-[4.25rem] text-right sm:w-24" align="right" />
                <SortHeader label="Elo" sortKey="elo" sort={sort} onSort={toggleSort} className="w-[3.75rem] text-right sm:w-20" align="right" />
                <th scope="col" className="hidden w-9 sm:table-cell">
                  <span className="sr-only">Open team</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((team) => (
                <tr key={team.id} className="group relative bg-surface transition-colors hover:bg-surface-2 has-[a:focus-visible]:bg-surface-2">
                  <th scope="row" className="py-2.5 pl-3 pr-1 text-left font-normal sm:pl-4 sm:pr-2">
                    {/* The link is stretched over the row (after:inset-0), so
                        the whole row is the click target while the table keeps
                        its real row/cell semantics. */}
                    <Link
                      href={`/teams/${team.id}`}
                      className="flex min-w-0 items-center gap-2.5 after:absolute after:inset-0 focus-visible:outline-none sm:gap-3"
                    >
                      <TeamFlag name={team.name} fifaCode={team.fifa_code} size="md" />
                      <span className="min-w-0">
                        {/* Wraps at word boundaries rather than truncating: the
                            name is the row's identity and must stay readable. */}
                        <span className="block font-semibold leading-tight text-foreground">{team.name}</span>
                        <span className="block text-[11px] tracking-wider text-fg-subtle">{team.fifa_code ?? "—"}</span>
                      </span>
                    </Link>
                  </th>
                  <td className="px-1.5 py-2.5 font-display text-lg font-semibold text-fg-muted sm:px-2">{team.wc2026_group ?? "—"}</td>
                  <td className="hidden px-2 py-2.5 text-fg-muted md:table-cell">{team.confederation ?? "—"}</td>
                  <td className="px-1.5 py-2.5 text-right font-semibold text-foreground sm:px-2">
                    {team.fifa_ranking != null ? team.fifa_ranking : <span className="font-normal text-fg-subtle">—</span>}
                  </td>
                  <td className="px-1.5 py-2.5 text-right text-fg-muted sm:px-2">
                    {team.elo_rating != null ? team.elo_rating : <span className="text-fg-subtle">—</span>}
                  </td>
                  <td className="hidden pr-3 text-fg-subtle sm:table-cell">
                    <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" aria-hidden="true" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Result count: announced politely so a screen-reader user hears the
          effect of typing or filtering. */}
      <p role="status" aria-live="polite" className="text-xs text-fg-subtle">
        {isLoading || error
          ? ""
          : `Showing ${rows.length} of ${data?.length ?? 0} teams. FIFA rank and Elo are the pre-tournament values held for each team.`}
      </p>
    </div>
  );
}

function GroupChip({ label, spoken, active, onClick }: { label: string; spoken?: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={spoken}
      className={cn(
        "flex h-9 min-w-9 shrink-0 items-center justify-center rounded-md border px-2.5 text-sm font-semibold transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "border-primary bg-primary text-primary-ink"
          : "border-border bg-surface text-fg-muted hover:border-border-strong hover:text-foreground"
      )}
    >
      {label}
    </button>
  );
}

function SortHeader({
  label,
  short,
  sortKey,
  sort,
  onSort,
  className,
  align = "left",
}: {
  label: string;
  /** Shorter label below `sm`, where the column is narrow. */
  short?: string;
  sortKey: SortKey;
  sort: { key: SortKey; dir: SortDir };
  onSort: (key: SortKey) => void;
  className?: string;
  align?: "left" | "right";
}) {
  const active = sort.key === sortKey;
  const Arrow = sort.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th scope="col" aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"} className={cn("px-2 py-1", className)}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={cn(
          "eyebrow inline-flex h-9 items-center gap-1 rounded transition-colors hover:text-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          align === "right" && "flex-row-reverse",
          active && "text-foreground"
        )}
      >
        {short ? (
          <>
            <span className="sm:hidden">{short}</span>
            <span className="hidden sm:inline">{label}</span>
          </>
        ) : (
          label
        )}
        {/* The arrow keeps its space when inactive so headers do not shift. */}
        <Arrow className={cn("h-3 w-3", active ? "text-primary" : "invisible")} aria-hidden="true" />
      </button>
    </th>
  );
}
