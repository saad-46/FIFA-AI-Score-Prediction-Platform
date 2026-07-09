import { cn } from "@/lib/utils";

interface StatComparisonBarProps {
  label: string;
  homeLabel: string;
  awayLabel: string;
  homeValue: number;
  awayValue: number;
  /** For ranking-style stats where a smaller number is better (e.g. FIFA rank #1 beats #10). */
  lowerIsBetter?: boolean;
  formatValue?: (value: number) => string;
  className?: string;
}

/**
 * A single flexible comparison bar — covers Elo rating, FIFA ranking, or any
 * other head-to-head numeric stat, rather than three near-identical
 * single-purpose card components.
 */
export function StatComparisonBar({
  label,
  homeLabel,
  awayLabel,
  homeValue,
  awayValue,
  lowerIsBetter = false,
  formatValue,
  className,
}: StatComparisonBarProps) {
  const total = homeValue + awayValue || 1;
  const homePct = (homeValue / total) * 100;
  const homeBetter = lowerIsBetter ? homeValue < awayValue : homeValue > awayValue;
  const awayBetter = lowerIsBetter ? awayValue < homeValue : awayValue > homeValue;
  const fmt = formatValue ?? ((v: number) => v.toLocaleString());

  return (
    <div className={cn("space-y-1.5", className)}>
      <p className="text-center text-xs font-medium text-fg-muted">{label}</p>
      <div className="flex items-center gap-3 text-sm">
        <span className={cn("w-16 shrink-0 text-right font-semibold", homeBetter ? "text-primary" : "text-foreground")}>
          {fmt(homeValue)}
        </span>
        <div
          role="img"
          aria-label={`${homeLabel} ${fmt(homeValue)} vs ${awayLabel} ${fmt(awayValue)}`}
          className="flex h-2 flex-1 overflow-hidden rounded-full bg-surface-2"
        >
          <div className="h-full bg-primary transition-all duration-700 ease-out" style={{ width: `${homePct}%` }} />
          <div className="h-full bg-accent transition-all duration-700 ease-out" style={{ width: `${100 - homePct}%` }} />
        </div>
        <span className={cn("w-16 shrink-0 font-semibold", awayBetter ? "text-accent" : "text-foreground")}>
          {fmt(awayValue)}
        </span>
      </div>
      <div className="flex justify-between text-[11px] text-fg-muted">
        <span className="truncate">{homeLabel}</span>
        <span className="truncate">{awayLabel}</span>
      </div>
    </div>
  );
}
