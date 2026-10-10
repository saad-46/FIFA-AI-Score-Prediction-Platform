"use client";

import { useEffect, useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * The stages a prediction request goes through, in order.
 *
 * Kept deliberately general. Which model answers depends on the server's
 * configuration, so the steps describe what every engine does — read the
 * teams' records, estimate goals, derive scorelines, settle the probabilities —
 * and name no technique or feature count the active engine might not use. A
 * loading state that narrates work the product does not perform is the same
 * kind of problem as a fabricated statistic.
 */
const STEPS = [
  "Reading both teams' match records",
  "Estimating expected goals",
  "Working out the scoreline distribution",
  "Settling win, draw and loss probabilities",
];

/** Honest pacing: the backend does not stream progress, so this advances on a
 *  timer and holds on the last step until the response arrives. */
export function ReasoningLoader() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 900);
    return () => clearInterval(timer);
  }, []);

  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className="rounded-lg border border-border bg-surface px-5 py-8 sm:px-8"
    >
      <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
        Working out the prediction…
      </p>
      {/* The list is decorative detail for sighted users; the status line above
          is what a screen reader announces, once. */}
      <ol className="mt-5 space-y-2.5" aria-hidden="true">
        {STEPS.map((label, i) => (
          <li
            key={label}
            className={cn(
              "flex items-center gap-2.5 text-sm transition-colors",
              i < step ? "text-fg-muted" : i === step ? "text-foreground" : "text-fg-subtle"
            )}
          >
            <span className="flex h-4 w-4 shrink-0 items-center justify-center">
              {i < step ? (
                <Check className="h-4 w-4 text-primary" />
              ) : (
                <span className={cn("h-1.5 w-1.5 rounded-full", i === step ? "bg-primary" : "bg-border-strong")} />
              )}
            </span>
            {label}
          </li>
        ))}
      </ol>
    </div>
  );
}
