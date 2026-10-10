"use client";

import { useState } from "react";
import { playerImageSrc } from "@/lib/player-images";
import { cn } from "@/lib/utils";

/**
 * The circular player mark used in the dense 26-player roster.
 *
 * Same two-state contract as `PlayerPortrait` — a local photograph from
 * `public/teams/<team>/<player>.webp` when one exists, a typographic monogram
 * when one does not — so the roster and the key-player cards never disagree
 * about a player. Photographs are added team by team through the ingest
 * script, so a roster normally mixes both states.
 *
 * `PlayerPortrait` is the framed, portrait-format version used where the image
 * is meant to dominate. This one stays small and circular: at roster scale a
 * 3:4 crop would just be a thumbnail of a face with no room for the crop to
 * mean anything.
 *
 * Decorative in both states — the player's name is always rendered as text
 * beside it.
 */

const SIZES = {
  sm: "h-10 w-10 text-[11px]",
  md: "h-14 w-14 text-sm",
  lg: "h-24 w-24 text-2xl",
  xl: "h-32 w-32 text-3xl sm:h-40 sm:w-40 sm:text-4xl",
} as const;

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function PlayerAvatar({
  name,
  team,
  size = "md",
  className,
}: {
  name: string;
  /** Registry team name. Omitted where the caller has no team in hand — the
   *  avatar then always renders its monogram. */
  team?: string;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const src = team ? playerImageSrc(team, name) : null;
  const [failed, setFailed] = useState(false);

  if (src !== null && !failed) {
    return (
      // Plain <img>, matching TeamFlag and PlayerPortrait: a pre-optimised
      // static asset already in /public.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt=""
        aria-hidden="true"
        width={600}
        height={800}
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
        className={cn(
          "shrink-0 rounded-full border border-border bg-surface-2 object-cover object-top",
          SIZES[size],
          className
        )}
      />
    );
  }

  return (
    <span
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full",
        "border border-border bg-surface-2 font-semibold tracking-wide text-fg-subtle",
        SIZES[size],
        className
      )}
      aria-hidden="true"
    >
      <span className="relative">{initials(name)}</span>
    </span>
  );
}
