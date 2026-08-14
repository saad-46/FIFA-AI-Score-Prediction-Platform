"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { motion, useReducedMotion } from "framer-motion";
import { Search } from "lucide-react";
import { teamsApi } from "@/lib/api/teams";
import { getApiErrorMessage } from "@/lib/api/client";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { CardGridSkeleton } from "@/components/ui/page-skeletons";
import { getCountryFlag } from "@/components/football/team-identity";
import { cn } from "@/lib/utils";
import type { Team } from "@/types";

/**
 * The WC2026 team directory — all 48, alphabetically.
 *
 * Previously this rendered `getTopTeams(20)`, a win-rate leaderboard, so users
 * saw 20 of 48 with no indication the rest existed, ordered by performance
 * rather than by name. It now reads `/teams/wc2026`, which is scoped to the 48
 * qualifiers server-side (see `team_service.get_wc2026_teams` for why that
 * scoping — not deleting rows — is the correct fix for the "Central Spain"
 * class of entry).
 *
 * Search filters the loaded 48 in-memory rather than calling `/teams/search`:
 * that endpoint searches all 335 rows including non-national entities, which
 * is exactly what this page must not surface.
 */
export function TeamsView() {
  const [query, setQuery] = useState("");
  const reduceMotion = useReducedMotion();
  const { data, error, isLoading, mutate } = useSWR(
    "wc2026-team-directory",
    teamsApi.getWc2026Teams,
    { revalidateOnFocus: false }
  );

  const filtered = useMemo(() => {
    const teams = data ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return teams;
    // Name or FIFA code, so both "Brazil" and "BRA" find Brazil.
    return teams.filter(
      (team) =>
        team.name.toLowerCase().includes(q) ||
        (team.fifa_code ?? "").toLowerCase().includes(q)
    );
  }, [data, query]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-fg-muted" aria-hidden="true" />
          <Input
            placeholder="Search by team or code..."
            className="pl-9"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search teams by name or FIFA code"
          />
        </div>
        <p className="font-mono text-[11px] uppercase tracking-wider text-fg-muted">
          {isLoading ? "Loading" : `${filtered.length} of ${data?.length ?? 0} teams`}
        </p>
      </div>

      {isLoading ? (
        <CardGridSkeleton count={9} />
      ) : error ? (
        <ErrorState
          title="Couldn't load the teams"
          description={getApiErrorMessage(error)}
          onRetry={() => mutate()}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No teams found"
          description={`No 2026 team matches "${query}".`}
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((team, index) => (
            <motion.div
              key={team.id}
              initial={reduceMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.2,
                ease: "easeOut",
                delay: reduceMotion ? 0 : Math.min(index, 12) * 0.02,
              }}
            >
              <Wc2026TeamCard team={team} />
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

function Wc2026TeamCard({ team }: { team: Team }) {
  const flag = getCountryFlag(team.name, team.fifa_code ?? undefined);
  return (
    <Link
      href={`/teams/${team.id}`}
      className={cn(
        "group flex flex-col gap-3 rounded-lg border border-border bg-surface p-4",
        "transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:bg-surface-2/40",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span
            className="select-none text-2xl leading-none transition-transform duration-200 group-hover:scale-110"
            aria-hidden="true"
          >
            {flag}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{team.name}</p>
            <p className="font-mono text-[11px] uppercase tracking-wider text-fg-muted">
              {team.fifa_code ?? "—"}
            </p>
          </div>
        </div>
        {team.wc2026_group && (
          <span className="shrink-0 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-primary">
            Group {team.wc2026_group}
          </span>
        )}
      </div>

      <dl className="grid grid-cols-2 gap-2 border-t border-border/50 pt-2.5">
        <Stat label="FIFA rank" value={team.fifa_ranking != null ? `#${team.fifa_ranking}` : "N/A"} />
        <Stat label="Elo" value={team.elo_rating != null ? String(team.elo_rating) : "N/A"} />
      </dl>
    </Link>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-mono text-[10px] uppercase tracking-wider text-fg-muted">{label}</dt>
      <dd className="pt-0.5 font-mono text-sm font-semibold tabular-nums text-foreground">
        {value}
      </dd>
    </div>
  );
}
