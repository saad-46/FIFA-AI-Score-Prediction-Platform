"use client";

import { ShieldCheck } from "lucide-react";
import { PlayerPortrait } from "@/components/teams/player-portrait";
import { cn } from "@/lib/utils";
import type { Player } from "@/types";

/**
 * A card for one of the ~8 players the team profile leads with.
 *
 * Built like a football card rather than a database row: the portrait owns the
 * card, the identity sits over a gradient fade at its foot, and only the one or
 * two numbers that make the player notable come with it. The full column set
 * stays in the dialog — a card that tries to be a dashboard stops being
 * glanceable, and eight of them side by side become a spreadsheet.
 *
 * A keeper is described by saves and clean sheets rather than goals and
 * assists, because a line of zeroes says nothing true about a goalkeeper.
 *
 * Motion is CSS transition only, so it needs no hook, and every transform is
 * explicitly cancelled under `prefers-reduced-motion` — the global rule in
 * globals.css collapses transition *duration*, which would otherwise leave the
 * lift and zoom snapping into place instantly rather than not happening.
 */

/** Short label for the card, full label for the accessible name. */
type Stat = { label: string; long: string; value: string };

/**
 * The numbers that say why this player is on the page, chosen by position.
 *
 *   outfield     Apps · Starts · Goals · Assists
 *   goalkeeper   Apps · Starts · Saves · Clean sheets
 *
 * A slot is dropped when its value is zero or absent. The zeroes are real and
 * the dialog still shows every one of them, but "0 GOALS · 0 ASSISTS" is the
 * least informative thing a card can say about a centre-back who started every
 * match — it describes the shape of the dataset rather than the player. A
 * defender therefore reads "5 APPS · 5 STARTS", and a forward who scored reads
 * all four.
 *
 * Nothing is invented and nothing is rounded up. Appearances is the one stat
 * that is always present here, because the server-side ranking already
 * excludes anyone who never played.
 */
function headline(player: Player): Stat[] {
  const keeper = player.is_goalkeeper && player.gk_saves !== null;

  const candidates: (Stat & { raw: number | null })[] = [
    { label: "Apps", long: "appearances", value: String(player.games), raw: player.games },
    { label: "Starts", long: "starts", value: String(player.games_starts), raw: player.games_starts },
    ...(keeper
      ? [
          { label: "Saves", long: "saves", value: String(player.gk_saves), raw: player.gk_saves },
          {
            label: "Sheets",
            long: "clean sheets",
            value: String(player.gk_clean_sheets),
            raw: player.gk_clean_sheets,
          },
        ]
      : [
          { label: "Goals", long: "goals", value: String(player.goals), raw: player.goals },
          { label: "Assists", long: "assists", value: String(player.assists), raw: player.assists },
        ]),
  ];

  return candidates
    .filter((s) => s.raw !== null && s.raw !== 0)
    .map(({ label, long, value }) => ({ label, long, value }));
}

export function KeyPlayerCard({
  player,
  isCaptain,
  onSelect,
}: {
  player: Player;
  isCaptain: boolean;
  onSelect: () => void;
}) {
  const stats = headline(player);

  // Spelled out for assistive technology, because the visible stat labels are
  // abbreviated to fit the card ("Sheets" for clean sheets) and colour/position
  // alone should never be what communicates the captaincy.
  const spoken = [
    player.name,
    isCaptain ? "captain" : null,
    player.is_goalkeeper ? "goalkeeper" : null,
    player.position ?? "position not available",
    player.club ?? "club not available",
    ...stats.map((s) => `${s.value} ${s.long}`),
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-label={`${spoken}. View full statistics`}
      className={cn(
        "group @container relative block w-full overflow-hidden rounded-lg text-left",
        "border border-border bg-surface",
        // `translate`, not `transform`: Tailwind v4 lifts the card with the
        // standalone `translate` property, so transitioning `transform` would
        // leave the lift snapping into place instead of easing.
        "transition-[translate,border-color,box-shadow] duration-300 ease-out",
        "hover:-translate-y-1 hover:border-border-strong",
        "motion-reduce:transition-[border-color,box-shadow] motion-reduce:hover:translate-y-0",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      )}
    >
      <PlayerPortrait
        name={player.name}
        team={player.team}
        className="aspect-[3/4] w-full"
        mediaClassName={cn(
          "transition-transform duration-500 ease-out group-hover:scale-[1.04]",
          "motion-reduce:transition-none motion-reduce:group-hover:scale-100"
        )}
        monogramClassName="text-3xl sm:text-4xl"
      />

      {/* Readability fade. From md up the caption overlays the foot of the
          portrait, so a fade keeps a two-line name legible. Below md the
          caption has its own panel under the portrait (see below), because a
          165px-wide card has no part of its image to spare: the overlay
          covered the face. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 hidden h-[62%] bg-gradient-to-t from-surface via-surface/90 to-transparent md:block"
      />

      {/* Role tag. Text, not colour or position, says who is the captain and
          who is the goalkeeper. */}
      {(isCaptain || player.is_goalkeeper) && (
        <span className="absolute left-2.5 top-2.5 inline-flex items-center gap-1 rounded border border-border-strong bg-surface/90 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-foreground">
          {isCaptain ? (
            <>
              <ShieldCheck className="h-3 w-3 text-primary" aria-hidden="true" />
              Captain
            </>
          ) : (
            "Goalkeeper"
          )}
        </span>
      )}

      <div
        className={cn(
          // Phones: a normal block under the portrait. md and up: overlaid.
          "border-t border-border p-3 md:absolute md:inset-x-0 md:bottom-0 md:border-t-0 md:p-4",
          "md:transition-[translate] md:duration-300 md:ease-out md:group-hover:-translate-y-0.5",
          "motion-reduce:transition-none motion-reduce:group-hover:translate-y-0"
        )}
      >
        <p className="line-clamp-2 font-display text-xl font-semibold uppercase leading-[0.95] tracking-wide text-foreground md:text-2xl">
          {player.name}
        </p>
        <p className="truncate pt-1.5 text-xs text-fg-muted">
          {[player.position, player.club].filter(Boolean).join(" · ") || "—"}
        </p>

        {stats.length > 0 && (
          // Two-up until the card is genuinely wide enough for four. The
          // breakpoint is lg, not sm: at 768px the grid is three cards across
          // and a quarter-card is ~50px, which clips "ASSISTS". At 1024 the
          // same three-across grid gives ~285px of content and four fit.
          <div className="grid grid-cols-2 gap-x-3 gap-y-2 pt-3 @[17rem]:grid-cols-4">
            {stats.map((s) => (
              <div key={s.label} className="min-w-0">
                <span className="scoreline text-xl text-foreground">{s.value}</span>
                <span className="block pt-0.5 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                  {s.label}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </button>
  );
}
