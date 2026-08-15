"use client";

import useSWR from "swr";
import Link from "next/link";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { squadApi } from "@/lib/api/squad";
import { getApiErrorMessage } from "@/lib/api/client";
import { PlayerAvatar } from "@/components/teams/player-avatar";
import { SquadGrid } from "@/components/teams/squad-grid";
import { ErrorState } from "@/components/ui/error-state";
import { CardGridSkeleton } from "@/components/ui/page-skeletons";
import type { Player } from "@/types";

/**
 * Squad half of the team detail page: hero, captain feature, and the 26-card
 * grid.
 *
 * One request for the whole thing (`/teams/{id}/squad`) — the grid never fetches
 * per card. The squad dataset is static per deploy, so revalidation is off for
 * the same reason the WC2026 tournament hooks turn it off.
 */

function stat(value: number | null | undefined): string {
  return value === null || value === undefined ? "Not available" : String(value);
}

function CaptainStat({ label, value }: { label: string; value: string }) {
  const missing = value === "Not available";
  return (
    <div>
      <p className="font-mono text-[9px] uppercase tracking-widest text-fg-muted">{label}</p>
      <p
        className={
          missing
            ? "pt-0.5 text-xs text-fg-muted/70"
            : "pt-0.5 font-mono text-lg font-bold tabular-nums text-foreground"
        }
      >
        {value}
      </p>
    </div>
  );
}

function CaptainFeature({ captain }: { captain: Player }) {
  const keeper = captain.is_goalkeeper && captain.gk_saves !== null;
  return (
    <div className="flex flex-col items-center gap-5 rounded-xl border border-border/60 bg-surface/40 p-6 text-center backdrop-blur-sm sm:flex-row sm:items-center sm:gap-7 sm:text-left">
      <PlayerAvatar name={captain.name} size="xl" />
      <div className="min-w-0 flex-1">
        <p className="flex items-center justify-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-primary sm:justify-start">
          <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
          Captain
        </p>
        <h2 className="pt-1.5 text-2xl font-bold tracking-tight text-foreground">
          {captain.name}
        </h2>
        <p className="pt-1 text-sm text-fg-muted">
          {captain.position ?? "Position not available"}
          {" · "}
          {captain.club ?? "Club not available"}
        </p>
        <div className="grid grid-cols-2 gap-4 pt-4 sm:grid-cols-4">
          <CaptainStat label="Apps" value={stat(captain.games)} />
          <CaptainStat label="Minutes" value={stat(captain.minutes)} />
          {keeper ? (
            <>
              <CaptainStat label="Saves" value={stat(captain.gk_saves)} />
              <CaptainStat label="Clean sheets" value={stat(captain.gk_clean_sheets)} />
            </>
          ) : (
            <>
              <CaptainStat label="Goals" value={stat(captain.goals)} />
              <CaptainStat label="Assists" value={stat(captain.assists)} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export function TeamSquadSection({ teamId }: { teamId: string }) {
  const { data, error, isLoading, mutate } = useSWR(
    ["team-squad", teamId],
    () => squadApi.getSquad(teamId),
    { revalidateOnFocus: false, revalidateIfStale: false }
  );

  if (isLoading) return <CardGridSkeleton count={6} />;

  if (error) {
    return (
      <ErrorState
        title="Couldn't load the squad"
        description={getApiErrorMessage(error)}
        onRetry={() => mutate()}
      />
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-8">
      <nav aria-label="Breadcrumb">
        <Link
          href="/teams"
          className="inline-flex items-center gap-1.5 rounded text-xs text-fg-muted transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          All teams
        </Link>
      </nav>

      {/* No team name/flag heading here on purpose: the detail page's existing
          hero already carries the crest, name, code, rank, Elo and group. This
          section adds only what is new — squad totals, the captain and the
          roster — so the page gains a squad rather than growing a second
          header. */}
      <div className="flex flex-wrap gap-6 border-b border-border/30 pb-5">
        <CaptainStat label="Squad" value={String(data.squad_size)} />
        <CaptainStat label="Goals" value={String(data.total_goals)} />
        <CaptainStat label="Assists" value={String(data.total_assists)} />
        <CaptainStat label="Minutes" value={String(data.total_minutes)} />
      </div>

      {data.captain ? (
        <CaptainFeature captain={data.captain} />
      ) : (
        // Never guessed from seniority or fame.
        <p className="rounded-xl border border-dashed border-border/60 bg-surface/20 px-6 py-5 text-sm text-fg-muted">
          Captain not available for this team.
        </p>
      )}

      <SquadGrid players={data.players} />

      {/* Say plainly where the numbers come from, and that photographs are a
          known gap rather than something still loading. */}
      <p className="border-t border-border/30 pt-4 text-xs leading-relaxed text-fg-muted">
        Squad and per-player statistics come from the committed 2026 player dataset;{" "}
        {data.players_with_appearances} of {data.squad_size} players have at least one appearance,
        and a metric is shown only where it exists. Player photographs are not available — no
        licensed image source is wired into this product, so cards show initials rather than a
        stand-in picture.
      </p>
    </div>
  );
}
