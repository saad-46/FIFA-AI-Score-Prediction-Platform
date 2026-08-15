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

const PAGE_SIZE = 12;

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
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-fg-muted" aria-hidden="true" />
          <Input
            placeholder="Filter by team..."
            className="pl-9"
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
          <SelectTrigger className="w-full sm:w-56">
            <SelectValue placeholder="All tournaments" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All tournaments</SelectItem>
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
          <p className="text-sm text-fg-muted sm:ml-auto">
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
            Loading historical World Cup matches…
          </p>
          <ListSkeleton count={PAGE_SIZE} />
        </div>
      ) : error ? (
        <ErrorState title="Couldn't load matches" description={getApiErrorMessage(error)} onRetry={() => mutate()} />
      ) : !data || data.data.length === 0 ? (
        <EmptyState icon={Search} title="No matches found" description="Try a different team or tournament filter." />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {data.data.map((match, i) => (
              <MatchCard key={match.id} match={match} delay={i * 0.02} />
            ))}
          </div>
          <Pagination page={page} totalPages={data.total_pages} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
