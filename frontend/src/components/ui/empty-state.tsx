import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

/**
 * The single empty-state pattern for the app — replaces the copy-pasted
 * "Connect API to load..." placeholder text that used to be duplicated
 * across teams/matches/analytics/tournaments pages.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 text-center",
        className
      )}
    >
      <Icon className="h-12 w-12 text-fg-muted/40 mb-4" aria-hidden="true" />
      <p className="text-fg-muted font-medium">{title}</p>
      {description && (
        <p className="text-fg-muted/70 text-sm mt-1 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
