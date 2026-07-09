import { cn } from "@/lib/utils";

interface TeamIdentityProps {
  name: string;
  fifaCode?: string;
  /** "avatar" = circular monogram only (compact lists, tables).
   *  "chip"   = monogram + FIFA code pill (dense grids, group cards). */
  variant?: "avatar" | "chip";
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizeClass = {
  sm: "h-6 w-6 text-[10px]",
  md: "h-8 w-8 text-xs",
  lg: "h-10 w-10 text-sm",
};

/**
 * No real crest/flag imagery exists in the dataset (Team.logo_url is
 * unpopulated for every team) — this deliberately renders a monogram
 * instead of fabricating flag emoji/images that could be wrong or missing.
 * Swap the fallback for <AvatarImage src={logo_url}> once real assets exist.
 */
export function TeamIdentity({ name, fifaCode, variant = "avatar", size = "md", className }: TeamIdentityProps) {
  const initials = fifaCode ?? name.slice(0, 3).toUpperCase();
  const monogram = (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-cyan-500 font-bold text-white",
        sizeClass[size]
      )}
      aria-hidden="true"
    >
      {initials.slice(0, 3)}
    </div>
  );

  if (variant === "avatar") {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        {monogram}
        <span className="truncate text-sm font-medium text-foreground">{name}</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2 py-1 pl-1 pr-2.5",
        className
      )}
    >
      {monogram}
      <span className="truncate text-xs font-medium text-foreground">{fifaCode ?? name}</span>
    </div>
  );
}
