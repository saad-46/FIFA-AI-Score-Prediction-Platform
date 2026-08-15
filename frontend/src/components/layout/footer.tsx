import Link from "next/link";
import { Trophy } from "lucide-react";
import { FeedbackWidget } from "@/components/feedback/feedback-widget";

export function Footer() {
  return (
    <footer className="border-t border-border bg-background py-8 mt-auto">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-primary/30 bg-primary/15">
              <Trophy className="h-3.5 w-3.5 text-primary" />
            </div>
            <span className="text-sm font-semibold text-foreground">
              FIFA<span className="text-primary">AI</span>
            </span>
          </div>
          <p className="text-xs text-fg-muted">
            AI-powered football score predictions. For entertainment purposes only.
          </p>
          <div className="flex items-center gap-4 text-xs text-fg-muted">
            {/* Anonymous feedback lives here rather than in a popup: findable
                when someone wants it, invisible otherwise. */}
            <FeedbackWidget />
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
