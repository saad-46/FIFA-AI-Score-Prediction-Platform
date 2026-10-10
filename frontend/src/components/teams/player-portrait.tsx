"use client";

import { useState } from "react";
import { playerImageSrc } from "@/lib/player-images";
import { cn } from "@/lib/utils";

/**
 * A player's photograph, or the monogram that stands in for one.
 *
 * Two states, both designed rather than one designed and one degraded:
 *
 *   * A local photograph exists (`public/teams/<team>/<player>.webp`) — it is
 *     rendered from that same-origin path and nothing else. This component
 *     cannot emit an external URL; `playerImageSrc` only ever returns a path
 *     under /teams, so player imagery stays at zero third-party requests.
 *   * No photograph exists — a typographic monogram on the same plate the
 *     photograph would have stood on. Photographs are added team by team
 *     through `npm run ingest:player-images`, so some players will always be
 *     in this state; it is a normal, designed state of the UI and is styled as
 *     a deliberate treatment, not as a missing asset.
 *
 * The photographs are cut-outs with a transparent background, so both states
 * share one backdrop (`Plate`): the portrait stands in front of the same lit
 * surface the monogram sits on, and a team with half its photographs still
 * reads as one set of cards.
 *
 * Because the lookup is manifest-driven, a player without a photograph never
 * causes a request at all — there is no 404, no broken-image flash and no
 * layout shift between the two states.
 *
 * Always decorative: every call site renders the player's name as adjacent
 * text, so announcing the portrait too would just repeat it.
 */

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** The backdrop both states share: one soft light from above, on the surface token. */
function Plate() {
  return (
    <span
      aria-hidden="true"
      className="absolute inset-0 bg-[radial-gradient(ellipse_90%_70%_at_50%_0%,color-mix(in_srgb,var(--primary)_14%,transparent),transparent_70%)]"
    />
  );
}

function Monogram({
  name,
  className,
  mediaClassName,
}: {
  name: string;
  className?: string;
  mediaClassName?: string;
}) {
  return (
    <span className={cn("absolute inset-0 grid place-items-center", mediaClassName)}>
      <span className={cn("relative font-display font-semibold tracking-[0.08em] text-fg-subtle", className)}>
        {initials(name)}
      </span>
    </span>
  );
}

export function PlayerPortrait({
  name,
  team,
  className,
  mediaClassName,
  monogramClassName,
  eager = false,
}: {
  name: string;
  /** Registry team name — half of the image key, e.g. "Brazil". */
  team: string;
  /** Sizing and framing come from the caller (aspect ratio, radius, border). */
  className?: string;
  /**
   * Applied to whichever of the two states is rendering, so a caller's hover
   * zoom works on the monogram as well as on a photograph.
   */
  mediaClassName?: string;
  /** Applied to the monogram glyph only, so a caller can scale the initials. */
  monogramClassName?: string;
  /** Above-the-fold portraits (the captain) skip lazy loading. */
  eager?: boolean;
}) {
  const src = playerImageSrc(team, name);
  // A manifest entry whose file has gone missing is a real bug, unlike an
  // absent entry — fall back rather than leave a broken image on the card.
  const [failed, setFailed] = useState(false);

  return (
    <div className={cn("relative isolate overflow-hidden bg-surface-2", className)} aria-hidden="true">
      <Plate />
      {src !== null && !failed ? (
        // Plain <img>, matching TeamFlag: these are pre-optimised static assets
        // already in /public, and routing them through the image optimiser
        // would add a hop without reducing bytes.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt=""
          // Intrinsic size of every ingested file (600x800). With the
          // caller's aspect-ratio box this reserves the space before load.
          width={600}
          height={800}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          onError={() => setFailed(true)}
          className={cn("relative h-full w-full object-cover object-top", mediaClassName)}
        />
      ) : (
        <Monogram name={name} className={monogramClassName} mediaClassName={mediaClassName} />
      )}
    </div>
  );
}
