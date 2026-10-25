import Link from "next/link";
import { FeedbackWidget } from "@/components/feedback/feedback-widget";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-border py-6">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="font-display text-lg font-bold uppercase leading-none tracking-wider text-foreground">
            FIFA 26 <span className="text-primary">Intelligence</span>
          </span>
          <p className="text-center text-xs text-fg-muted">
            Model-based football forecasts. Not affiliated with FIFA. For entertainment only.
            <span className="mt-1 block">
              Fan-made project. Characters are original stylized figures, not official likenesses. Not affiliated with
              any football association, club or player.
            </span>
          </p>
          <div className="flex items-center gap-4 text-xs text-fg-muted">
            {/* Anonymous feedback lives here rather than in a popup: findable
                when someone wants it, invisible otherwise. */}
            <FeedbackWidget />
            <Link href="/about" className="inline-flex min-h-11 items-center px-2 hover:text-foreground transition-colors">
              About
            </Link>
            {/* No Privacy / Terms links here. They pointed at /privacy and
                /terms, neither of which exists — every page in the product was
                shipping two links that 404. Rather than invent legal copy, the
                links are gone until real pages exist; /about already carries the
                entertainment-only and not-affiliated-with-FIFA disclaimers. */}
          </div>
        </div>
      </div>
    </footer>
  );
}
