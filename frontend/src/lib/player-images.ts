import { PLAYER_IMAGE_KEYS } from "@/lib/player-images.generated";

/**
 * Local player photographs — resolution only, never fetching.
 *
 * The product makes zero external image requests, and that is a hard rule
 * rather than a preference: FIFA publishes no consumable squad-image API, and
 * hot-linking any third party would put an uncontrolled request on every card
 * with unclear licensing. See PLAYER_IMAGE_POLICY in backend/app/data/players.py.
 *
 * What this module adds is the missing half of that policy: a place for
 * *licensed* photographs to live inside the repository, so a photo can be
 * dropped in without touching a component.
 *
 *   frontend/public/teams/<team-slug>/<player-slug>.webp
 *
 * e.g. public/teams/brazil/vinicius-junior.webp
 *
 * Resolution is manifest-driven, not optimistic. `PLAYER_IMAGE_KEYS` is
 * generated from what is actually on disk by `scripts/build-player-images.mjs`,
 * so a player with no photograph renders the monogram directly and the browser
 * never issues a request that would 404. This mirrors how `TeamFlag` handles
 * the bundled flag SVGs: an explicit set distinguishes "no asset exists" (a
 * normal, designed state) from "the asset failed to load" (a real bug).
 */

/** Public directory that holds every player photograph. */
export const PLAYER_IMAGE_ROOT = "/teams";

/**
 * Filesystem-safe slug for a team or player name.
 *
 * Diacritics are folded rather than dropped ("Vinícius Júnior" ->
 * "vinicius-junior", "Türkiye" -> "turkiye", "Côte d'Ivoire" ->
 * "cote-d-ivoire") so the on-disk name is typeable on any keyboard. This must
 * stay byte-for-byte identical to `slugify` in scripts/build-player-images.mjs
 * — `scripts/audit-player-images.mjs` fails the build-time audit if the two
 * ever disagree.
 */
const NON_COMPOSING: Record<string, string> = {
  // Letters that NFD cannot decompose into base + combining mark, so they
  // survive the diacritic strip and would otherwise be lost to [^a-z0-9].
  ø: "o",
  đ: "d",
  ð: "d",
  þ: "th",
  ł: "l",
  ß: "ss",
  æ: "ae",
  œ: "oe",
};

export function slugify(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[øđðþłßæœ]/g, (c) => NON_COMPOSING[c] ?? c)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Manifest key for a player: "<team-slug>/<player-slug>". */
export function playerImageKey(team: string, player: string): string {
  return `${slugify(team)}/${slugify(player)}`;
}

/**
 * The local path a player's photograph would occupy, whether or not it exists.
 * Exposed so the audit script and the drop-in documentation agree on one
 * convention instead of two.
 */
export function playerImagePath(team: string, player: string): string {
  return `${PLAYER_IMAGE_ROOT}/${playerImageKey(team, player)}.webp`;
}

/**
 * A local photograph exists for this player.
 *
 * False is the ordinary case today — no licensed source is wired in, so the
 * manifest is empty and every card renders its monogram. It is not an error
 * state and must not be presented as one.
 */
export function hasPlayerImage(team: string, player: string): boolean {
  return PLAYER_IMAGE_KEYS.has(playerImageKey(team, player));
}

/**
 * The photograph to render, or null when the player has none.
 * Always a same-origin path under /teams — this function can never return an
 * external URL, which is what keeps the "0 external image requests" guarantee
 * a property of the code rather than a promise in a comment.
 */
export function playerImageSrc(team: string, player: string): string | null {
  return hasPlayerImage(team, player) ? playerImagePath(team, player) : null;
}
