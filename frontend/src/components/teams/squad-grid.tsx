"use client";

import { useState } from "react";
import { PlayerAvatar } from "@/components/teams/player-avatar";
import { PlayerDialog } from "@/components/teams/player-dialog";
import { cn } from "@/lib/utils";
import type { Player } from "@/types";

/**
 * The 26-player squad grid.
 *
 * Each card is a real <button> so it is reachable and activatable by keyboard,
 * and opens the same dialog a click does. Hover is deliberately restrained —
 * the lift, border and surface shift already used by the team and match cards —
 * because this is a roster, not a landing page.
 *
 * Which four statistics a card shows depends on the player: a keeper who has
 * kept goal gets saves and clean sheets instead of goals and assists, and a
 * squad member with no appearances gets a plain "No appearances" line rather
 * than four zeroes that would imply he played and did nothing.
 */

function fmt(value: number | null): string {
  return value === null || value === undefined ? "—" : String(value);
}

function CardStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="font-mono text-[9px] uppercase tracking-wider text-fg-muted">{label}</p>
      <p className="truncate font-mono text-sm font-semibold tabular-nums text-foreground">
        {value}
      </p>
    </div>
  );
}

function PlayerCard({ player, onSelect }: { player: Player; onSelect: () => void }) {
  const played = (player.games ?? 0) > 0;
  // A keeper only gets keeper stats if he actually kept goal; otherwise he
  // falls through to the outfield block, which will itself be suppressed when
  // he has no appearances.
  const keeperStats = player.is_goalkeeper && player.gk_saves !== null;

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-label={`${player.name}, ${player.position ?? "position not available"}. View full statistics`}
      className={cn(
        "group flex w-full flex-col gap-3 rounded-lg border border-border bg-surface p-4 text-left",
        "transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:bg-surface-2/40",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      )}
    >
      <div className="flex items-start gap-3">
        <PlayerAvatar
          name={player.name}
          className="transition-transform duration-200 group-hover:scale-105"
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-foreground">{player.name}</p>
          <p className="truncate text-xs text-fg-muted">
            {player.club ?? "Club not available"}
          </p>
          <div className="flex items-center gap-2 pt-1">
            <span className="rounded border border-border/60 bg-surface-2/60 px-1.5 font-mono text-[9px] uppercase tracking-wider text-fg-muted">
              {player.position ?? "—"}
            </span>
            {player.age !== null && (
              <span className="font-mono text-[10px] text-fg-muted">{player.age}y</span>
            )}
          </div>
        </div>
      </div>

      {played ? (
        <div className="grid grid-cols-4 gap-2 border-t border-border/30 pt-2.5">
          <CardStat label="Apps" value={fmt(player.games)} />
          <CardStat label="Mins" value={fmt(player.minutes)} />
          {keeperStats ? (
            <>
              <CardStat label="Saves" value={fmt(player.gk_saves)} />
              <CardStat label="Clean" value={fmt(player.gk_clean_sheets)} />
            </>
          ) : (
            <>
              <CardStat label="Goals" value={fmt(player.goals)} />
              <CardStat label="Assists" value={fmt(player.assists)} />
            </>
          )}
        </div>
      ) : (
        // Not "0 goals, 0 assists" — he has not played, which is a different
        // fact and the only one we actually know.
        <p className="border-t border-border/30 pt-2.5 text-xs text-fg-muted">
          No appearances on record
        </p>
      )}
    </button>
  );
}

export function SquadGrid({ players }: { players: Player[] }) {
  const [selected, setSelected] = useState<Player | null>(null);

  return (
    <section aria-labelledby="squad-heading" className="space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="squad-heading" className="font-mono text-sm uppercase tracking-widest text-foreground">
          Squad
        </h2>
        <p className="font-mono text-[11px] uppercase tracking-wider text-fg-muted">
          {players.length} players
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {players.map((p) => (
          <PlayerCard key={`${p.team}-${p.name}`} player={p} onSelect={() => setSelected(p)} />
        ))}
      </div>

      <PlayerDialog player={selected} onOpenChange={(open) => !open && setSelected(null)} />
    </section>
  );
}
