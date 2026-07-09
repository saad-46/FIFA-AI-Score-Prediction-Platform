import { cn } from "@/lib/utils";

interface BracketTeamSlot {
  name: string;
  code?: string;
  score?: number;
  winner?: boolean;
}

interface BracketNodeProps {
  home: BracketTeamSlot | null;
  away: BracketTeamSlot | null;
  className?: string;
}

/** A single fixture slot within a bracket column. Unresolved slots (e.g. a
 * Round-of-16 TBD) render as "TBD" rather than being omitted. This is the
 * atomic building block for a full bracket layout — composing multiple
 * rounds with connecting lines is page-level work, not a primitive. */
export function BracketNode({ home, away, className }: BracketNodeProps) {
  return (
    <div className={cn("w-48 overflow-hidden rounded-lg border border-border bg-surface", className)}>
      <BracketRow slot={home} />
      <div className="h-px bg-border" />
      <BracketRow slot={away} />
    </div>
  );
}

function BracketRow({ slot }: { slot: BracketTeamSlot | null }) {
  return (
    <div
      className={cn(
        "flex items-center justify-between px-2.5 py-1.5 text-xs",
        slot?.winner && "bg-primary/10"
      )}
    >
      <span className={cn("truncate", slot?.winner ? "font-semibold text-foreground" : "text-fg-muted")}>
        {slot ? slot.name : "TBD"}
      </span>
      {slot?.score !== undefined && (
        <span className={cn("font-mono font-semibold", slot.winner ? "text-primary" : "text-fg-muted")}>
          {slot.score}
        </span>
      )}
    </div>
  );
}
