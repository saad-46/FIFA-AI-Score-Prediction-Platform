import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  /** Right-aligned slot for a page-level action or status chip. */
  actions?: React.ReactNode;
  className?: string;
}

/**
 * The standard page header.
 *
 * Seven routes had already converged on the same markup — icon, mono uppercase
 * title, muted one-line description — but each re-declared it, and /about and
 * /profile had drifted to a plain non-mono heading. Centralising it makes the
 * hierarchy identical everywhere and gives page-level actions one place to sit.
 *
 * Server-renderable: no client hooks, so pages stay static where they already are.
 */
export function PageHeader({
  title,
  description,
  icon: Icon,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn("flex flex-wrap items-start justify-between gap-4", className)}>
      <div className="min-w-0">
        <h1 className="flex items-center gap-2.5 font-mono text-2xl font-bold uppercase tracking-tight text-foreground">
          {Icon && <Icon className="h-6 w-6 shrink-0 text-primary" aria-hidden="true" />}
          {title}
        </h1>
        {description && (
          <p className="mt-1 max-w-2xl text-sm text-fg-muted">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}
