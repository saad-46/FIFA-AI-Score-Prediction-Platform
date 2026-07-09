import Link from "next/link";
import { Trophy } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-border bg-background py-8 mt-auto">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500">
              <Trophy className="h-3.5 w-3.5 text-white" />
            </div>
            <span className="text-sm font-semibold text-foreground">
              FIFA<span className="text-primary">AI</span>
            </span>
          </div>
          <p className="text-xs text-fg-muted">
            AI-powered football score predictions. For entertainment purposes only.
          </p>
          <div className="flex items-center gap-4 text-xs text-fg-muted">
            <Link href="/about" className="hover:text-foreground transition-colors">
              About
            </Link>
            <Link href="/privacy" className="hover:text-foreground transition-colors">
              Privacy
            </Link>
            <Link href="/terms" className="hover:text-foreground transition-colors">
              Terms
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
