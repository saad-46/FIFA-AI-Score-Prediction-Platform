"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { squadApi } from "@/lib/api/squad";
import { getApiErrorMessage } from "@/lib/api/client";
import { PlayerAvatar } from "@/components/teams/player-avatar";
import { KeyPlayerCard } from "@/components/teams/key-player-card";
import { PlayerDialog } from "@/components/teams/player-dialog";
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

/**
 * The captain, given the weight a team profile gives its captain.
 *
 * Deliberately the largest thing on the page after the team name: an oversized
 * monogram, his name at display size, and four headline numbers — rather than
 * one more card in a grid. Keeper captains get saves and clean sheets in place
 * of goals and assists.
 */
function CaptainFeature({
  captain,
  onOpen,
}: {
  captain: Player;
  onOpen: () => void;
}) {
  const keeper = captain.is_goalkeeper && captain.gk_saves !== null;
  return (
    <section
      aria-labelledby="captain-heading"
      className="relative overflow-hidden rounded-2xl border border-border/60 bg-surface/40 p-6 backdrop-blur-sm sm:p-8"
    >
      {/* One soft cyan wash, matching the prediction result card. No blob. */}
      <div
        className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-primary/5 blur-3xl"
        aria-hidden="true"
      />
      <div className="relative flex flex-col items-center gap-6 text-center sm:flex-row sm:items-center sm:gap-8 sm:text-left">
        <PlayerAvatar name={captain.name} size="xl" />
        <div className="min-w-0 flex-1">
          <p className="flex items-center justify-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-primary sm:justify-start">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            Captain
          </p>
          <h2
            id="captain-heading"
            className="pt-2 text-3xl font-bold tracking-tight text-foreground sm:text-4xl"
          >
            {captain.name}
          </h2>
          <p className="pt-1.5 text-sm text-fg-muted">
            {captain.position ?? "Position not available"}
            {" · "}
            {captain.club ?? "Club not available"}
            {captain.age !== null && ` · ${captain.age} years`}
          </p>
          <div className="grid grid-cols-2 gap-5 pt-5 sm:grid-cols-4">
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
          <button
            type="button"
            onClick={onOpen}
            className="mt-5 rounded-lg border border-border/60 bg-surface-2/50 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wider text-fg-muted transition-colors hover:border-primary/40 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Full statistics
          </button>
        </div>
      </div>
    </section>
  );
}

export function TeamSquadSection({ teamId }: { teamId: string }) {
  // The captain feature and the key-player grid share one dialog, so opening a
  // player from either place lands in the same detail view.
  const [selected, setSelected] = useState<Player | null>(null);
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
        <CaptainFeature captain={data.captain} onOpen={() => setSelected(data.captain)} />
      ) : (
        // Never guessed from seniority or fame.
        <p className="rounded-xl border border-dashed border-border/60 bg-surface/20 px-6 py-5 text-sm text-fg-muted">
          Captain not available for this team.
        </p>
      )}

      {/* Key players lead. The full 26 are still reachable below, but they are
          no longer the primary view — a profile should open on the players who
          actually featured, not on an undifferentiated roster. */}
      {data.key_players.length > 0 && (
        <section aria-labelledby="key-players-heading" className="space-y-4">
          <div className="flex items-baseline justify-between gap-3">
            <h2
              id="key-players-heading"
              className="font-mono text-sm uppercase tracking-widest text-foreground"
            >
              Key Players
            </h2>
            <p className="font-mono text-[11px] uppercase tracking-wider text-fg-muted">
              {data.key_players.length} of {data.squad_size}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
            {data.key_players.map((p) => (
              <KeyPlayerCard
                key={`key-${p.name}`}
                player={p}
                isCaptain={p.name === data.captain?.name}
                onSelect={() => setSelected(p)}
              />
            ))}
          </div>
          <p className="text-xs leading-relaxed text-fg-muted">
            Ranked from this squad&apos;s own record — captain first, then by appearances, starts
            and goal contribution, with saves and clean sheets standing in for goalkeepers. Players
            with no appearances are never listed here.
          </p>
        </section>
      )}

      {/* Full squad, secondary and collapsed by default. */}
      <details className="group rounded-xl border border-border/50 bg-surface/20">
        <summary className="cursor-pointer list-none rounded-xl px-5 py-4 font-mono text-xs uppercase tracking-widest text-fg-muted transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          Full squad · {data.squad_size} players
        </summary>
        <div className="px-5 pb-5">
          <SquadGrid players={data.players} />
        </div>
      </details>

      <PlayerDialog player={selected} onOpenChange={(open) => !open && setSelected(null)} />

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
