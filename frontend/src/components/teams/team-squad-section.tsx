"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { ShieldCheck } from "lucide-react";
import { squadApi } from "@/lib/api/squad";
import { getApiErrorMessage } from "@/lib/api/client";
import { hasPlayerImage } from "@/lib/player-images";
import { PlayerPortrait } from "@/components/teams/player-portrait";
import { KeyPlayerCard } from "@/components/teams/key-player-card";
import { PlayerDialog } from "@/components/teams/player-dialog";
import { SquadGrid } from "@/components/teams/squad-grid";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { SectionHeader } from "@/components/ui/section";
import type { Player } from "@/types";

/**
 * Squad half of the team profile: the captain, the key players and the full
 * roster.
 *
 * One request for the whole thing (`/teams/{id}/squad`) — nothing fetches per
 * card. The squad dataset is static per deploy, so revalidation is off for the
 * same reason the WC2026 tournament hooks turn it off.
 */

/**
 * The captain's headline numbers, by position, with empty slots dropped.
 *
 * Appearances and minutes always earn their place — they are why he is on the
 * page. Goals, assists, saves and clean sheets appear only when they happened,
 * on the same reasoning as the key-player cards: a defender captain reading
 * "0 goals · 0 assists" is a fact about the column list, not about him. Every
 * one of those zeroes is still there in the dialog.
 */
function captainStats(captain: Player): { label: string; value: string }[] {
  const keeper = captain.is_goalkeeper && captain.gk_saves !== null;
  const rows: { label: string; raw: number | null }[] = [
    { label: "Appearances", raw: captain.games },
    { label: "Minutes", raw: captain.minutes },
    ...(keeper
      ? [
          { label: "Saves", raw: captain.gk_saves },
          { label: "Clean sheets", raw: captain.gk_clean_sheets },
        ]
      : [
          { label: "Goals", raw: captain.goals },
          { label: "Assists", raw: captain.assists },
        ]),
  ];
  return rows
    .filter((r, i) => r.raw !== null && (i < 2 || r.raw !== 0))
    .map((r) => ({ label: r.label, value: String(r.raw) }));
}

/**
 * The captain, given the weight a team profile gives its captain: a portrait
 * plate on one side, his name at display size and his headline numbers on the
 * other, rather than one more card in a grid.
 */
function CaptainFeature({ captain, onOpen }: { captain: Player; onOpen: () => void }) {
  const headline = captainStats(captain);
  return (
    <section aria-labelledby="captain-heading" className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="grid md:grid-cols-[minmax(0,17rem)_minmax(0,1fr)]">
        {/* The plate runs to the card's edge and bleeds off its foot; the
            portrait is the subject, not a thumbnail inside a frame. */}
        <div className="relative mx-auto w-full max-w-[17rem] md:max-w-none">
          <PlayerPortrait
            name={captain.name}
            team={captain.team}
            eager
            className="aspect-[4/5] w-full md:aspect-auto md:h-full md:min-h-[21rem]"
            monogramClassName="text-6xl"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-surface to-transparent md:inset-y-0 md:left-auto md:right-0 md:h-auto md:w-1/4 md:bg-gradient-to-l"
          />
        </div>

        <div className="flex min-w-0 flex-col justify-center px-5 pb-6 pt-2 text-center sm:px-8 md:py-8 md:text-left">
          <p className="flex items-center justify-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-primary md:justify-start">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Captain
          </p>
          <h2
            id="captain-heading"
            className="mt-2 text-balance font-display text-4xl font-bold uppercase leading-[0.95] tracking-wide text-foreground sm:text-6xl"
          >
            {captain.name}
          </h2>
          <p className="mt-3 text-sm text-fg-muted">
            {[captain.position, captain.club, captain.age !== null ? `${captain.age} years` : null]
              .filter(Boolean)
              .join(" · ") || "Details not available"}
          </p>

          {headline.length > 0 && (
            <dl className="mt-6 flex flex-wrap justify-center gap-x-9 gap-y-4 md:justify-start">
              {headline.map((s) => (
                <div key={s.label}>
                  <dt className="eyebrow">{s.label}</dt>
                  <dd className="scoreline mt-1 text-3xl text-foreground">{s.value}</dd>
                </div>
              ))}
            </dl>
          )}

          <div className="mt-6">
            <Button variant="outline" onClick={onOpen} aria-label={`View full statistics for ${captain.name}, captain`}>
              Full statistics
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

export function TeamSquadSection({ teamId }: { teamId: string }) {
  // The captain feature and the key-player grid share one dialog, so opening a
  // player from either place lands in the same detail view.
  const [selected, setSelected] = useState<Player | null>(null);
  // Whatever the user activated to open the dialog, so ESC hands focus back to
  // it instead of to <body>. Captured in the handler, where activeElement is
  // still the card the user was on.
  const openerRef = useRef<HTMLElement | null>(null);
  const openPlayer = (player: Player | null) => {
    openerRef.current = document.activeElement as HTMLElement | null;
    setSelected(player);
  };
  const { data, error, isLoading, mutate } = useSWR(["team-squad", teamId], () => squadApi.getSquad(teamId), {
    revalidateOnFocus: false,
    revalidateIfStale: false,
  });

  if (isLoading) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading squad">
        <Skeleton className="h-80 w-full rounded-lg" />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="aspect-[3/4] w-full rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return <ErrorState title="Couldn't load the squad" description={getApiErrorMessage(error)} onRetry={() => mutate()} />;
  }

  if (!data) return null;

  const captainName = data.captain?.name ?? null;
  // The captain already has the feature above; listing him again as the first
  // card would spend the grid's best slot repeating it.
  const keyPlayers = data.key_players.filter((p) => p.name !== captainName);

  // How many of the players shown with a portrait frame actually have a
  // photograph on disk. Read from the generated manifest, so the sentence
  // below is true for whatever has been ingested, with no copy to maintain.
  const featured = [...(data.captain ? [data.captain] : []), ...keyPlayers];
  const withPhoto = featured.filter((p) => hasPlayerImage(p.team, p.name)).length;
  const squadWithPhoto = data.players.filter((p) => hasPlayerImage(p.team, p.name)).length;

  return (
    <div className="space-y-10">
      {data.captain ? (
        <CaptainFeature captain={data.captain} onOpen={() => openPlayer(data.captain)} />
      ) : (
        // Never guessed from seniority or fame.
        <p className="rounded-lg border border-dashed border-border px-5 py-4 text-sm text-fg-muted">
          No captain is recorded for this team.
        </p>
      )}

      {/* Key players lead. The full 26 follow below, but a profile should open
          on the players who actually featured, not on an undifferentiated
          roster. */}
      {keyPlayers.length > 0 && (
        <section aria-labelledby="key-players-heading" className="space-y-4">
          <SectionHeader
            id="key-players-heading"
            title="Key players"
            meta="By appearances, starts and goal contribution"
          />
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
            {keyPlayers.map((p) => (
              <KeyPlayerCard key={`key-${p.name}`} player={p} isCaptain={false} onSelect={() => openPlayer(p)} />
            ))}
          </div>
          <p className="max-w-3xl text-xs leading-relaxed text-fg-subtle">
            Chosen from this squad&apos;s own record: appearances, then starts and goal contribution, with saves and
            clean sheets standing in for goalkeepers, and always including a goalkeeper. A player with no
            appearances is never listed here.
          </p>
        </section>
      )}

      <section aria-labelledby="squad-heading" className="space-y-5">
        <SectionHeader id="squad-heading" title="Full squad" meta={`${data.squad_size} players`} />
        <dl className="flex flex-wrap gap-x-10 gap-y-4">
          {[
            { label: "Goals", value: data.total_goals },
            { label: "Assists", value: data.total_assists },
            { label: "Minutes", value: data.total_minutes.toLocaleString() },
            { label: "Players used", value: `${data.players_with_appearances} of ${data.squad_size}` },
          ].map((t) => (
            <div key={t.label}>
              <dt className="eyebrow">{t.label}</dt>
              <dd className="scoreline mt-1 text-2xl text-foreground">{t.value}</dd>
            </div>
          ))}
        </dl>
        <SquadGrid players={data.players} captainName={captainName} />
      </section>

      <PlayerDialog
        player={selected}
        isCaptain={selected !== null && selected.name === captainName}
        restoreFocusRef={openerRef}
        onOpenChange={(open) => !open && setSelected(null)}
      />

      {/* Say plainly where the numbers and the pictures come from. */}
      <p className="max-w-3xl border-t border-border pt-4 text-xs leading-relaxed text-fg-subtle">
        Squad and player statistics come from the 2026 player dataset held with this site; a figure is shown only
        where it exists.{" "}
        {squadWithPhoto === 0
          ? "No photographs have been added for this team yet, so players are shown by their initials."
          : `Photographs are held for ${squadWithPhoto} of ${data.squad_size} players${
              featured.length > 0 ? ` (${withPhoto} of the ${featured.length} featured above)` : ""
            }; the rest are shown by their initials until one is added.`}{" "}
        Every image is served from this site, never from a third party.
      </p>
    </div>
  );
}
