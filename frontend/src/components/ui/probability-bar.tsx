import { cn } from "@/lib/utils";

interface ProbabilityBarProps {
  label: string;
  value: number; // 0–1
  tone?: "primary" | "win" | "draw" | "loss" | "accent";
  showValue?: boolean;
  className?: string;
}

const toneClass: Record<NonNullable<ProbabilityBarProps["tone"]>, string> = {
  primary: "bg-primary",
  win: "bg-win",
  draw: "bg-draw",
  loss: "bg-loss",
  accent: "bg-accent",
};

/** Labeled, animated 0–1 probability bar. Server-renderable — the fill
 * transition is pure CSS, no JS animation needed. Reused for win/draw/loss
 * splits, tournament stage probabilities, and any other percentage. */
export function ProbabilityBar({
  label,
  value,
  tone = "primary",
  showValue = true,
  className,
}: ProbabilityBarProps) {
  const pct = Math.round(value * 100);
  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex justify-between text-xs font-mono uppercase tracking-wider">
        <span className="text-foreground">{label}</span>
        {showValue && <span className="font-semibold text-fg-muted">{pct}%</span>}
      </div>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2"
      >
        <div
          className={cn("h-full rounded-full transition-all duration-700 ease-out", toneClass[tone])}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
