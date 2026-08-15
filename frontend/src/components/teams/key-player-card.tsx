"use client";

import { ShieldCheck } from "lucide-react";
import { PlayerAvatar } from "@/components/teams/player-avatar";
import { cn } from "@/lib/utils";
import type { Player } from "@/types";

/**
 * A card for one of the ~8 players the team profile leads with.
 *
 * Carries only what identifies a player and the one or two numbers that make
 * him notable — the full column set stays in the dialog. A keeper is described
 * by saves and clean sheets rather than goals and assists, because a line of
 * zeroes says nothing true about a goalkeeper.
 *
 * Motion is the same restrained lift/scale/border already used by the team and
 * match cards, and all of it is CSS transition rather than JS animation, so it
 * follows the media query without a hook.
 */

function headline(player: Player): { label: string; value: string }[] {
  const out: { label: string; value: string }[] = [];
  const keeper = player.is_goalkeeper && player.gk_saves !== null;

  if (keeper) {
    if (player.gk_saves !== null) out.push({ label: "Saves", value: String(player.gk_saves) });
    if (player.gk_clean_sheets !== null)
      out.push({ label: "Clean sheets", value: String(player.gk_clean_sheets) });
  } else {
    if (player.goals !== null) out.push({ label: "Goals", value: String(player.goals) });
    if (player.assists !== null) out.push({ label: "Assists", value: String(player.assists) });
  }
  // Everyone in this list has played, so appearances is always meaningful and
  // is a good backstop for a defender with no goal contribution.
  if (out.length < 2 && player.games !== null)
    out.push({ label: "Apps", value: String(player.games) });
  return out.slice(0, 2);
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

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-label={`${player.name}, ${player.position ?? "position not available"}${
        isCaptain ? ", captain" : ""
      }. View full statistics`}
      className={cn(
        "group relative flex w-full flex-col items-center gap-3 overflow-hidden rounded-xl p-5 text-center",
        "border border-border/60 bg-surface/40 backdrop-blur-sm",
        "transition-all duration-200 motion-reduce:transition-none",
        "hover:-translate-y-1 hover:border-primary/40 hover:bg-surface-2/50 hover:shadow-lg hover:shadow-black/20",
        "motion-reduce:hover:translate-y-0",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      )}
    >
      {isCaptain && (
        <span className="absolute left-3 top-3 inline-flex items-center gap-1 rounded border border-primary/30 bg-primary/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-primary">
          <ShieldCheck className="h-3 w-3" aria-hidden="true" />
          Captain
        </span>
      )}

      <PlayerAvatar
        name={player.name}
        size="lg"
        className="transition-transform duration-300 group-hover:scale-105 motion-reduce:transition-none motion-reduce:group-hover:scale-100"
      />

      <div className="min-w-0 w-full">
        <p className="truncate text-sm font-semibold text-foreground">{player.name}</p>
        <p className="truncate pt-0.5 text-xs text-fg-muted">
          {player.club ?? "Club not available"}
        </p>
        <span className="mt-2 inline-block rounded border border-border/60 bg-surface-2/60 px-1.5 font-mono text-[9px] uppercase tracking-wider text-fg-muted">
          {player.position ?? "—"}
        </span>
      </div>

      {stats.length > 0 && (
        <div className="flex w-full items-start justify-center gap-5 border-t border-border/30 pt-3">
          {stats.map((s) => (
            <div key={s.label}>
              <p className="font-mono text-lg font-bold tabular-nums text-foreground">{s.value}</p>
              <p className="font-mono text-[9px] uppercase tracking-wider text-fg-muted">
                {s.label}
              </p>
            </div>
          ))}
        </div>
      )}
    </button>
  );
}
