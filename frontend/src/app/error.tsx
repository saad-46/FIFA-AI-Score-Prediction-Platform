"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertOctagon } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center px-4">
      <AlertOctagon className="h-12 w-12 text-loss/70 mb-4" aria-hidden="true" />
      <h1 className="text-xl font-semibold text-foreground">Something went wrong</h1>
      <p className="text-fg-muted text-sm mt-2 max-w-sm">
        An unexpected error occurred. You can try again, or head back home.
      </p>
      <div className="flex gap-3 mt-6">
        <Button variant="outline" onClick={reset}>
          Try again
        </Button>
        <Button variant="gradient" asChild>
          <Link href="/">Go home</Link>
        </Button>
      </div>
    </div>
  );
}
