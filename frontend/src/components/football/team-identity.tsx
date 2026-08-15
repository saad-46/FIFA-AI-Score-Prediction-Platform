import { cn } from "@/lib/utils";
import { TeamFlag } from "@/components/football/team-flag";

interface TeamIdentityProps {
  name: string;
  fifaCode?: string;
  /** "avatar" = Circular/square monogram or flag (compact lists, tables).
   *  "chip"   = Flag badge + FIFA code pill (dense grids, group cards). */
  variant?: "avatar" | "chip";
  size?: "sm" | "md" | "lg";
  className?: string;
}

// The emoji FLAG_MAP and getCountryFlag() that lived here are gone: they are
// unreferenced now that every flag renders through TeamFlag's bundled SVGs,
// and leaving a working-looking emoji helper in the tree invites a future
// component to reintroduce flags that render as bare letters on Windows.

/** Maps this component's sizes onto TeamFlag's. */
const flagSize = { sm: "sm", md: "md", lg: "lg" } as const;

export function TeamIdentity({ name, fifaCode, variant = "avatar", size = "md", className }: TeamIdentityProps) {
  // Renders through TeamFlag (bundled SVG) rather than the emoji helper below:
  // Windows has no country-flag glyphs, so every consumer of TeamIdentity —
  // group cards, the simulation probability table, team detail — was showing
  // bare letters like "US" instead of a flag. This was missed when the other
  // call sites were migrated.
  const flagDisplay = <TeamFlag name={name} fifaCode={fifaCode} size={flagSize[size]} />;

  if (variant === "avatar") {
    return (
      <div className={cn("flex items-center gap-3", className)}>
        {flagDisplay}
        <span className="truncate text-sm font-medium text-foreground tracking-tight">{name}</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded border border-border bg-surface/50 py-1 pl-1.5 pr-2.5 shadow-sm backdrop-blur-sm",
        className
      )}
    >
      {flagDisplay}
      <span className="truncate text-xs font-mono font-bold uppercase tracking-wider text-foreground">
        {fifaCode ?? name.slice(0, 3).toUpperCase()}
      </span>
    </div>
  );
}
