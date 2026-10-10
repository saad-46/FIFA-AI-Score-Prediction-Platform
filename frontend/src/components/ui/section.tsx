import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface SectionHeaderProps {
  title: string;
  /** Context for the heading: a count, a scope, a date range. */
  meta?: React.ReactNode;
  /** Optional "see everything" link on the right. */
  href?: string;
  linkLabel?: string;
  /** Heading level. Pages own the h1; sections default to h2. */
  as?: "h2" | "h3";
  id?: string;
  className?: string;
}

/**
 * The one section heading. A rule under the title carries the structure, so
 * sections do not each need to be wrapped in their own bordered card to read
 * as separate.
 */
export function SectionHeader({ title, meta, href, linkLabel, as: Tag = "h2", id, className }: SectionHeaderProps) {
  return (
    <div className={cn("flex items-end justify-between gap-4 border-b border-border pb-2.5", className)}>
      <div className="flex min-w-0 flex-1 items-baseline gap-3">
        <Tag id={id} className="font-display text-xl font-semibold uppercase leading-none tracking-wide text-foreground">
          {title}
        </Tag>
        {/* Below sm the title and the link need the row; the meta is context, not content. */}
        {meta && <span className="hidden truncate text-xs text-fg-subtle sm:inline">{meta}</span>}
      </div>
      {href && (
        <Link
          href={href}
          className="group -my-2 inline-flex min-h-9 shrink-0 items-center gap-1 rounded px-1 text-xs font-semibold text-primary hover:text-primary-hover"
        >
          {linkLabel ?? "View all"}
          <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
        </Link>
      )}
    </div>
  );
}

interface MetricProps {
  label: string;
  value: React.ReactNode;
  /** One short line of definition or scope under the value. */
  hint?: React.ReactNode;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const metricValue = {
  sm: "text-xl",
  md: "text-3xl",
  lg: "text-5xl",
} as const;

/**
 * A labelled figure. No icon tile and no coloured border: the number is the
 * content. Rendered as a term/description pair so screen readers announce the
 * label with its value; wrap a group of these in a <dl>.
 */
export function Metric({ label, value, hint, size = "md", className }: MetricProps) {
  return (
    <div className={cn("min-w-0", className)}>
      <dt className="eyebrow">{label}</dt>
      <dd className={cn("scoreline mt-1.5 text-foreground", metricValue[size])}>{value}</dd>
      {hint && <dd className="mt-1 text-xs leading-snug text-fg-subtle">{hint}</dd>}
    </div>
  );
}
