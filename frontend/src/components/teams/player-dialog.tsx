"use client";

import type { RefObject } from "react";
import { ShieldCheck } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PlayerPortrait } from "@/components/teams/player-portrait";
import { cn } from "@/lib/utils";
import type { Player } from "@/types";

/**
 * Full statistics for one player.
 *
 * Sections are built from what the player actually has, not from the column
 * list: a section with no populated metric is not rendered at all, so a squad
 * member who never played shows appearances and nothing else rather than five
 * headings full of dashes.
 *
 * The accessibility contract here is Radix's and is deliberately left intact —
 * `aria-modal`, the focus trap, ESC-to-close and restore-focus-on-close all come
 * from `DialogContent`. The one thing this dialog was missing is a resolving
 * `aria-describedby`: the identity line below is now a real `DialogDescription`,
 * so the dialog announces who it is about rather than just its title.
 */

/** null/undefined -> "Not available". A real 0 is a fact and is shown as 0. */
function show(value: number | null | undefined, suffix = ""): string {
  if (value === null || value === undefined) return "Not available";
  return `${Number.isInteger(value) ? value : value.toFixed(2)}${suffix}`;
}

function has(...values: (number | null | undefined)[]): boolean {
  return values.some((v) => v !== null && v !== undefined);
}

function StatRow({ label, value }: { label: string; value: string }) {
  const missing = value === "Not available";
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <dt className="text-xs text-fg-muted">{label}</dt>
      <dd
        className={cn(
          "font-mono text-sm tabular-nums",
          missing ? "text-xs text-fg-subtle" : "font-semibold text-foreground"
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-md border border-border bg-surface-2 p-4">
      <h3 className="eyebrow pb-1">{title}</h3>
      <dl className="divide-y divide-border">{children}</dl>
    </section>
  );
}

export function PlayerDialog({
  player,
  isCaptain = false,
  restoreFocusRef,
  onOpenChange,
}: {
  player: Player | null;
  /** Shown as an explicit badge — never inferred from ordering or colour. */
  isCaptain?: boolean;
  /**
   * The card that opened the dialog, so focus can be handed back to it.
   *
   * This dialog is opened from state rather than from a `DialogTrigger`, so
   * Radix has no trigger to restore focus to and ESC was dropping the user
   * onto <body> — from there the next Tab restarts at the top of the document,
   * which for a keyboard user means losing their place in an eight-card grid
   * every time they close a player. The opener is captured by the caller in
   * its click handler, where `document.activeElement` is still the card.
   */
  restoreFocusRef?: RefObject<HTMLElement | null>;
  onOpenChange: (open: boolean) => void;
}) {
  // A keeper who actually kept goal is presented as a keeper. One who never
  // played falls through to the outfield layout, where the has() guards leave
  // him with just his (empty) appearance block rather than fake sections.
  const keeperView = player?.is_goalkeeper === true && player.gk_saves !== null;
  return (
    <Dialog open={player !== null} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-2xl border-border bg-surface"
        onCloseAutoFocus={(event) => {
          const opener = restoreFocusRef?.current;
          if (opener && document.contains(opener)) {
            event.preventDefault();
            opener.focus();
          }
        }}
      >
        {player && (
          <>
            <DialogHeader>
              <div className="flex items-center gap-4 sm:gap-5">
                <div className="relative shrink-0">
                  <PlayerPortrait
                    name={player.name}
                    team={player.team}
                    eager
                    className="aspect-[3/4] w-24 rounded-md border border-border sm:w-28"
                    monogramClassName="text-2xl sm:text-3xl"
                  />
                </div>
                <div className="min-w-0">
                  {isCaptain && (
                    <p className="flex items-center gap-1.5 pb-1.5 text-xs font-semibold uppercase tracking-wider text-primary">
                      <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                      Captain
                    </p>
                  )}
                  <DialogTitle className="pr-8 font-display text-3xl font-bold uppercase leading-none tracking-wide sm:text-4xl">
                    {player.name}
                  </DialogTitle>
                  <p className="pt-1.5 text-sm text-fg-muted">
                    {player.position ?? "Position not available"}
                    {" · "}
                    {player.club ?? "Club not available"}
                  </p>
                  {/* Doubles as the dialog's accessible description, so
                      aria-describedby resolves instead of dangling. */}
                  <DialogDescription className="pt-0.5 text-xs">
                    {player.team}
                    {player.age !== null && ` · Age ${player.age}`}
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>

            <div className="grid max-h-[60vh] grid-cols-1 gap-3 overflow-y-auto pt-2 sm:grid-cols-2">
              <Section title="Appearances">
                <StatRow label="Matches" value={show(player.games)} />
                <StatRow label="Starts" value={show(player.games_starts)} />
                <StatRow label="Minutes" value={show(player.minutes)} />
              </Section>

              {/* A keeper's attacking and creative lines are real zeroes, not
                  missing data — but a column of 0 shots and 0 crosses tells the
                  reader nothing about a goalkeeper. Show those sections only for
                  outfield players; the keeper gets the goalkeeping block below
                  instead. Defence and discipline stay: keepers do commit fouls
                  and collect cards. */}
              {!keeperView && has(player.goals, player.assists, player.shots, player.shots_on_target) && (
                <Section title="Attacking">
                  <StatRow label="Goals" value={show(player.goals)} />
                  <StatRow label="Assists" value={show(player.assists)} />
                  <StatRow label="Shots" value={show(player.shots)} />
                  <StatRow label="On target" value={show(player.shots_on_target)} />
                  {has(player.goals_per90) && (
                    <StatRow label="Goals / 90" value={show(player.goals_per90)} />
                  )}
                </Section>
              )}

              {!keeperView && has(player.crosses, player.fouled, player.offsides, player.assists_per90) && (
                <Section title="Creative">
                  <StatRow label="Crosses" value={show(player.crosses)} />
                  <StatRow label="Fouled" value={show(player.fouled)} />
                  <StatRow label="Offsides" value={show(player.offsides)} />
                  {has(player.assists_per90) && (
                    <StatRow label="Assists / 90" value={show(player.assists_per90)} />
                  )}
                </Section>
              )}

              {has(player.tackles_won, player.interceptions, player.fouls) && (
                <Section title="Defensive">
                  <StatRow label="Tackles won" value={show(player.tackles_won)} />
                  <StatRow label="Interceptions" value={show(player.interceptions)} />
                  <StatRow label="Fouls" value={show(player.fouls)} />
                </Section>
              )}

              {has(player.cards_yellow, player.cards_red) && (
                <Section title="Discipline">
                  <StatRow label="Yellow cards" value={show(player.cards_yellow)} />
                  <StatRow label="Red cards" value={show(player.cards_red)} />
                </Section>
              )}

              {/* Only for keepers who actually kept goal — 78 of the 136
                  goalkeepers on record have no goalkeeping data at all. */}
              {has(player.gk_saves, player.gk_clean_sheets, player.gk_goals_against) && (
                <Section title="Goalkeeping">
                  <StatRow label="Matches in goal" value={show(player.gk_games)} />
                  <StatRow label="Saves" value={show(player.gk_saves)} />
                  <StatRow label="Save %" value={show(player.gk_save_pct, "%")} />
                  <StatRow label="Clean sheets" value={show(player.gk_clean_sheets)} />
                  <StatRow label="Goals against" value={show(player.gk_goals_against)} />
                </Section>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
