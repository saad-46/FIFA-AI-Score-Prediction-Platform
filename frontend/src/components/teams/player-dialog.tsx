"use client";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PlayerAvatar } from "@/components/teams/player-avatar";
import { cn } from "@/lib/utils";
import type { Player } from "@/types";

/**
 * Full statistics for one player.
 *
 * Sections are built from what the player actually has, not from the column
 * list: a section with no populated metric is not rendered at all, so a squad
 * member who never played shows appearances and nothing else rather than five
 * headings full of dashes.
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
          missing ? "text-fg-muted/60 text-xs" : "font-semibold text-foreground"
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
    <section className="rounded-lg border border-border/50 bg-surface/30 p-4">
      <h3 className="pb-1 font-mono text-[10px] uppercase tracking-widest text-fg-muted">
        {title}
      </h3>
      <dl className="divide-y divide-border/30">{children}</dl>
    </section>
  );
}

export function PlayerDialog({
  player,
  onOpenChange,
}: {
  player: Player | null;
  onOpenChange: (open: boolean) => void;
}) {
  // A keeper who actually kept goal is presented as a keeper. One who never
  // played falls through to the outfield layout, where the has() guards leave
  // him with just his (empty) appearance block rather than fake sections.
  const keeperView = player?.is_goalkeeper === true && player.gk_saves !== null;

  return (
    <Dialog open={player !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl border-border/60 bg-surface/90 backdrop-blur-xl">
        {player && (
          <>
            <DialogHeader>
              <div className="flex items-center gap-4">
                <PlayerAvatar name={player.name} size="lg" />
                <div className="min-w-0">
                  <DialogTitle className="text-xl">{player.name}</DialogTitle>
                  <p className="pt-1 text-sm text-fg-muted">
                    {player.position ?? "Position not available"}
                    {" · "}
                    {player.club ?? "Club not available"}
                  </p>
                  <p className="pt-0.5 font-mono text-[11px] uppercase tracking-wider text-fg-muted">
                    {player.team}
                    {player.age !== null && ` · Age ${player.age}`}
                  </p>
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
