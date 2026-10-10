import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  /** Accepted for call-site compatibility; rendered small beside the label. */
  icon?: LucideIcon;
  trend?: { value: number; label: string };
  /** Accepted for call-site compatibility. Tiles no longer take a colour:
   *  green and red mean win and loss here and are not spent on decoration. */
  color?: "primary" | "accent" | "draw" | "loss";
  delay?: number;
}

/**
 * One headline figure.
 *
 * Previously a bordered card with a tinted icon tile in the corner and a
 * per-tile colour, four in a row on most pages. The figure is now the loudest
 * thing in the tile and the chrome is a single top rule. Use inside
 * `StatsRow`, which lays tiles out as one divided strip rather than four
 * separate boxes.
 *
 * Server Component: no client JS.
 */
export function StatsCard({ title, value, subtitle, icon: Icon, trend }: StatsCardProps) {
  return (
    <div className="min-w-0 bg-surface px-4 py-4 sm:px-5">
      <p className="eyebrow flex items-center gap-1.5">
        {Icon && <Icon className="h-3.5 w-3.5 text-fg-subtle" aria-hidden="true" />}
        {title}
      </p>
      <p className="scoreline mt-2 text-3xl text-foreground sm:text-4xl">{value}</p>
      {subtitle && <p className="mt-1.5 text-xs leading-snug text-fg-subtle">{subtitle}</p>}
      {trend && (
        <p className="mt-1.5 text-xs font-medium text-fg-muted">
          <span aria-hidden="true">{trend.value > 0 ? "▲" : "▼"}</span>{" "}
          <span className="sr-only">{trend.value > 0 ? "up" : "down"}</span>
          {Math.abs(trend.value)}% {trend.label}
        </p>
      )}
    </div>
  );
}

/**
 * A strip of StatsCards separated by hairlines. `gap-px` over a border-coloured
 * background draws the dividers, so the strip reads as one object at every
 * column count.
 */
export function StatsRow({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border lg:grid-cols-4",
        className
      )}
    >
      {children}
    </div>
  );
}
