"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}

/**
 * The single error-state pattern for the app. Use alongside
 * getApiErrorMessage() (lib/api/client.ts) to surface the real backend
 * message wherever a request can fail (network, 404, 422, 500, 503).
 */
export function ErrorState({
  title = "Something went wrong",
  description = "Please try again in a moment.",
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center py-12 text-center",
        className
      )}
    >
      <AlertTriangle className="h-12 w-12 text-loss/70 mb-4" aria-hidden="true" />
      <p className="text-foreground font-medium">{title}</p>
      <p className="text-fg-muted text-sm mt-1 max-w-sm">{description}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
