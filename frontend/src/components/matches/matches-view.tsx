"use client";

import { useState } from "react";
import useSWR from "swr";
import { Search } from "lucide-react";
import { matchesApi } from "@/lib/api/matches";
import { getApiErrorMessage } from "@/lib/api/client";
import { useDebounce } from "@/hooks/use-debounce";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Pagination } from "@/components/ui/pagination";
import { MatchCard } from "@/components/matches/match-card";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { ListSkeleton } from "@/components/ui/page-skeletons";
import type { Match } from "@/types";

const PAGE_SIZE = 20;

/** "Tue 6 Oct 2026": fixed locale and UTC, so server and client agree. */
function dayLabel(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

/** Preserves the server's order; only adjacent same-day matches are grouped. */
function groupByDay(matches: Match[]): [string, Match[]][] {
  const out: [string, Match[]][] = [];
  for (const m of matches) {
    const day = String(m.date).slice(0, 10);
    const last = out[out.length - 1];
    if (last && last[0] === day) last[1].push(m);
    else out.push([day, [m]]);
  }
  return out;
}

export function MatchesView() {
  const [page, setPage] = useState(1);
  const [team, setTeam] = useState("");
  const [tournament, setTournament] = useState("all");
  const debouncedTeam = useDebounce(team, 300);

  const { data: tournaments } = useSWR("match-tournaments", () => matchesApi.getTournaments());

  const { data, error, isLoading, mutate } = useSWR(
    ["matches", page, debouncedTeam, tournament],
    () =>
      matchesApi.getHistory(page, PAGE_SIZE, {
        team: debouncedTeam || undefined,
        tournament: tournament === "all" ? undefined : tournament,
      })
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative w-full sm:w-64">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" aria-hidden="true" />
          <Input
            type="search"
            placeholder="Filter by team"
            className="h-11 pl-9"
            value={team}
            onChange={(e) => {
              setTeam(e.target.value);
              setPage(1);
            }}
            aria-label="Filter matches by team"
          />
        </div>
        <Select
          value={tournament}
          onValueChange={(v) => {
            setTournament(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="h-11 w-full sm:w-64" aria-label="Filter by competition">
            <SelectValue placeholder="All competitions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All competitions</SelectItem>
            {(tournaments ?? []).map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {/* "49,389 matches" alone read as though the dozen cards below were the
            whole record. Name the window explicitly so the page never implies
            one page is the entire history. */}
        {data && data.total > 0 && (
          <p role="status" aria-live="polite" className="text-sm text-fg-muted sm:ml-auto">
            Showing {((page - 1) * PAGE_SIZE + 1).toLocaleString()}–
            {Math.min(page * PAGE_SIZE, data.total).toLocaleString()} of{" "}
            {data.total.toLocaleString()} matches
          </p>
        )}
      </div>

      {isLoading ? (
        <div>
          {/* Plain statement of what is being fetched — no fabricated stages,
              no percentage, no ETA. The wait is real (one round trip to the
              match table), so the skeleton stays. */}
          <p className="pb-3 text-sm text-fg-muted" role="status" aria-live="polite">
            Loading matches…
          </p>
          <ListSkeleton count={PAGE_SIZE} />
        </div>
      ) : error ? (
        <ErrorState title="Couldn't load matches" description={getApiErrorMessage(error)} onRetry={() => mutate()} />
      ) : !data || data.data.length === 0 ? (
        <EmptyState icon={Search} title="No matches found" description="Try a different team or competition." />
      ) : (
        <>
          {/* Grouped under a date heading, newest first: the date is said once
              per day instead of on every row. */}
          <div className="space-y-5">
            {groupByDay(data.data).map(([day, dayMatches]) => (
              <section key={day} aria-label={dayLabel(day)}>
                <h2 className="eyebrow mb-1.5">{dayLabel(day)}</h2>
                <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border">
                  {dayMatches.map((match) => (
                    <MatchCard key={match.id} match={match} />
                  ))}
                </ul>
              </section>
            ))}
          </div>
          <Pagination page={page} totalPages={data.total_pages} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
