"use client";

import { useRef, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { PlayerAvatar } from "@/components/teams/player-avatar";
import { PlayerDialog } from "@/components/teams/player-dialog";
import type { Player } from "@/types";

/**
 * The full squad, as a roster.
 *
 * Grouped by position and set as tables rather than as 26 cards. A roster is
 * read down a column — who has the most minutes, who scored — and a card grid
 * makes that comparison impossible while repeating "Apps / Mins / Goals /
 * Assists" twenty-six times. The key players above already get the portrait
 * treatment; this is the reference list beneath them.
 *
 * Each name is a real <button>, so every player is reachable by keyboard and
 * opens the same dialog a click does.
 *
 * Goalkeepers get saves and clean sheets where outfield players get goals and
 * assists. A player with no appearances shows a dash in every statistic column
 * rather than a row of zeroes that would imply he played and did nothing.
 */

const POSITION_GROUPS = [
  { key: "GK", title: "Goalkeepers" },
  { key: "DF", title: "Defenders" },
  { key: "MF", title: "Midfielders" },
  { key: "FW", title: "Forwards" },
] as const;

type GroupKey = (typeof POSITION_GROUPS)[number]["key"] | "OTHER";

/** "MF,FW" files under the first listed position; an unknown one under "Other". */
function groupOf(player: Player): GroupKey {
  if (player.is_goalkeeper) return "GK";
  const first = (player.position ?? "").split(/[,/ ]/)[0]?.toUpperCase();
  return first === "GK" || first === "DF" || first === "MF" || first === "FW" ? first : "OTHER";
}

function Figure({ value, played }: { value: number | null; played: boolean }) {
  if (!played || value === null || value === undefined) {
    return <span className="text-fg-subtle">—</span>;
  }
  return <>{value}</>;
}

function PositionTable({
  title,
  players,
  keeper,
  captainName,
  onSelect,
}: {
  title: string;
  players: Player[];
  keeper: boolean;
  captainName: string | null;
  onSelect: (p: Player) => void;
}) {
  const headingId = `squad-${title.toLowerCase()}`;
  return (
    <div>
      <h3 id={headingId} className="eyebrow mb-1.5 flex items-center gap-2">
        {title}
        <span className="font-normal tracking-normal text-fg-subtle">{players.length}</span>
      </h3>
      <div className="overflow-hidden rounded-lg border border-border">
        {/* Fixed layout: the five position tables share column widths, so
            figures line up down the whole squad rather than per table. */}
        <table aria-labelledby={headingId} className="w-full table-fixed text-sm">
          <thead className="border-b border-border bg-surface-2">
            <tr>
              <th scope="col" className="eyebrow py-2 pl-3 pr-2 text-left">Player</th>
              <th scope="col" className="eyebrow hidden w-[30%] px-2 py-2 text-left sm:table-cell">Club</th>
              <th scope="col" className="eyebrow hidden w-12 px-2 py-2 text-right md:table-cell">Age</th>
              <th scope="col" className="eyebrow w-12 px-2 py-2 text-right">
                <abbr title="Appearances" className="no-underline">Apps</abbr>
              </th>
              <th scope="col" className="eyebrow hidden w-14 px-2 py-2 text-right sm:table-cell">
                <abbr title="Minutes played" className="no-underline">Mins</abbr>
              </th>
              <th scope="col" className="eyebrow w-14 px-2 py-2 text-right">{keeper ? "Saves" : "Goals"}</th>
              <th scope="col" className="eyebrow w-16 py-2 pl-2 pr-3 text-right">
                {keeper ? (
                  <abbr title="Clean sheets" className="no-underline">Clean</abbr>
                ) : (
                  <abbr title="Assists" className="no-underline">Ast</abbr>
                )}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {players.map((p) => {
              const played = (p.games ?? 0) > 0;
              // Keeper columns only for a keeper who actually kept goal.
              const keeperStats = keeper && p.gk_saves !== null;
              const isCaptain = p.name === captainName;
              return (
                <tr key={`${p.team}-${p.name}`} className="group relative bg-surface transition-colors hover:bg-surface-2 has-[button:focus-visible]:bg-surface-2">
                  <th scope="row" className="py-2 pl-3 pr-2 text-left font-normal">
                    <button
                      type="button"
                      onClick={() => onSelect(p)}
                      aria-label={`${p.name}${isCaptain ? ", captain" : ""}. View full statistics`}
                      className="flex min-h-10 w-full min-w-0 items-center gap-3 text-left after:absolute after:inset-0 focus-visible:outline-none"
                    >
                      <PlayerAvatar name={p.name} team={p.team} size="sm" />
                      <span className="min-w-0">
                        <span className="flex items-center gap-1.5 font-semibold text-foreground">
                          <span className="leading-tight">{p.name}</span>
                          {isCaptain && <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />}
                        </span>
                        <span className="block text-xs leading-tight text-fg-subtle sm:hidden">{p.club ?? "Club not available"}</span>
                      </span>
                    </button>
                  </th>
                  <td className="hidden truncate px-2 py-2 text-fg-muted sm:table-cell">{p.club ?? "—"}</td>
                  <td className="hidden px-2 py-2 text-right text-fg-muted md:table-cell">{p.age ?? "—"}</td>
                  <td className="px-2 py-2 text-right font-semibold text-foreground">
                    {played ? p.games : <span className="font-normal text-fg-subtle">—</span>}
                  </td>
                  <td className="hidden px-2 py-2 text-right text-fg-muted sm:table-cell">
                    <Figure value={p.minutes} played={played} />
                  </td>
                  <td className="px-2 py-2 text-right text-foreground">
                    <Figure value={keeperStats ? p.gk_saves : keeper ? null : p.goals} played={played} />
                  </td>
                  <td className="py-2 pl-2 pr-3 text-right text-foreground">
                    <Figure value={keeperStats ? p.gk_clean_sheets : keeper ? null : p.assists} played={played} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function SquadGrid({
  players,
  captainName = null,
}: {
  players: Player[];
  /** So the roster marks the captain exactly as the key-player cards do — the
   *  same player must not be captain in one view and not the other. */
  captainName?: string | null;
}) {
  const [selected, setSelected] = useState<Player | null>(null);
  // See PlayerDialog#restoreFocusRef — ESC must return the user to the row
  // they opened, not to the top of the document.
  const openerRef = useRef<HTMLElement | null>(null);

  const select = (p: Player) => {
    openerRef.current = document.activeElement as HTMLElement | null;
    setSelected(p);
  };

  const byGroup = new Map<GroupKey, Player[]>();
  for (const p of players) {
    const key = groupOf(p);
    byGroup.set(key, [...(byGroup.get(key) ?? []), p]);
  }
  // Most-used players first within each position.
  for (const list of byGroup.values()) {
    list.sort((a, b) => (b.minutes ?? 0) - (a.minutes ?? 0) || a.name.localeCompare(b.name));
  }
  const other = byGroup.get("OTHER") ?? [];

  return (
    <div className="space-y-6">
      {POSITION_GROUPS.map(({ key, title }) => {
        const list = byGroup.get(key) ?? [];
        if (list.length === 0) return null;
        return (
          <PositionTable key={key} title={title} players={list} keeper={key === "GK"} captainName={captainName} onSelect={select} />
        );
      })}
      {other.length > 0 && (
        <PositionTable title="Position not recorded" players={other} keeper={false} captainName={captainName} onSelect={select} />
      )}

      <p className="text-xs text-fg-subtle">
        A dash means no appearance on record, or a figure the dataset does not hold. It is never a zero.
      </p>

      <PlayerDialog
        player={selected}
        isCaptain={selected !== null && selected.name === captainName}
        restoreFocusRef={openerRef}
        onOpenChange={(open) => !open && setSelected(null)}
      />
    </div>
  );
}
