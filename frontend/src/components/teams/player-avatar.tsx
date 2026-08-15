import { cn } from "@/lib/utils";

/**
 * The stand-in for a player photograph.
 *
 * There are no player photographs in this product and that is a documented
 * gap, not an oversight: the squad dataset has no image column, FIFA's official
 * squad pages render client-side with no public API behind them, and
 * hot-linking a third party would put an uncontrolled external request on every
 * card. Inventing or scraping images would break the same data-honesty rule
 * that governs the statistics, so the card shows a monogram instead and says
 * nothing it cannot support. See PLAYER_IMAGE_POLICY in app/data/players.py.
 *
 * Kept deliberately plain — initials on the existing surface tokens, with the
 * position as the only accent — so a squad grid reads as a roster rather than
 * a wall of missing images.
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
  size = "md",
  className,
}: {
  name: string;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full border border-border/60",
        "bg-surface-2/70 font-mono font-semibold tracking-wider text-fg-muted",
        SIZES[size],
        className
      )}
      // Decorative: the player's name is always rendered as text beside this,
      // so announcing the monogram too would just repeat it.
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}
