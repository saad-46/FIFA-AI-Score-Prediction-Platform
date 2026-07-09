import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: { value: number; label: string };
  color?: "primary" | "accent" | "draw" | "loss" | "purple";
  delay?: number;
}

const colorMap = {
  primary: { icon: "text-primary", bg: "bg-primary/10", border: "border-primary/20", trend: "text-primary" },
  accent: { icon: "text-accent", bg: "bg-accent/10", border: "border-accent/20", trend: "text-accent" },
  draw: { icon: "text-draw", bg: "bg-draw/10", border: "border-draw/20", trend: "text-draw" },
  loss: { icon: "text-loss", bg: "bg-loss/10", border: "border-loss/20", trend: "text-loss" },
  purple: {
    icon: "text-purple-400",
    bg: "bg-purple-500/10",
    border: "border-purple-500/20",
    trend: "text-purple-400",
  },
};

/** Server Component — the entrance animation is pure CSS so this never
 * needs to ship client JS. `delay` staggers a row of tiles via animation-delay. */
export function StatsCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  color = "primary",
  delay = 0,
}: StatsCardProps) {
  const colors = colorMap[color];

  return (
    <Card
      className={cn("border animate-in fade-in slide-in-from-bottom-2 fill-mode-both", colors.border)}
      style={{ animationDelay: `${delay}s`, animationDuration: "0.4s" }}
    >
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <p className="text-sm text-fg-muted">{title}</p>
            <p className="mt-1 text-2xl font-bold text-foreground">{value}</p>
            {subtitle && <p className="mt-0.5 text-xs text-fg-muted/70">{subtitle}</p>}
            {trend && (
              <p className={cn("mt-1 text-xs font-medium", colors.trend)}>
                {trend.value > 0 ? "↑" : "↓"} {Math.abs(trend.value)}% {trend.label}
              </p>
            )}
          </div>
          <div className={cn("rounded-lg p-2.5", colors.bg)}>
            <Icon className={cn("h-5 w-5", colors.icon)} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
