import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MarketingHeader } from "@/components/layout/marketing-header";
import { Footer } from "@/components/layout/footer";
import { LandingFinal } from "@/components/dashboard/landing-final";
import { IntroGate } from "@/components/intro/intro-gate";

const SECTIONS = [
  {
    href: "/tournaments",
    title: "The tournament",
    body: "All 104 matches: the knockout bracket, final group tables and the schedule with every score.",
  },
  {
    href: "/predict",
    title: "Match predictor",
    body: "Any two of the 48 teams. Win, draw and loss chances, expected goals and the likeliest scorelines.",
  },
  {
    href: "/teams",
    title: "Teams and squads",
    body: "Captain, key players and the full 26 for every team, with their tournament statistics.",
  },
  {
    href: "/tournaments?tab=backtest",
    title: "Model vs reality",
    body: "Every pre-tournament pick set against what happened, misses included.",
  },
] as const;

/**
 * Landing page.
 *
 * Server-rendered: the only client code is the block that loads the real final
 * from the API. The page says what the product is in one sentence and then
 * shows it, rather than opening on a full-screen slogan.
 */
export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      {/* Scroll-driven 3D intro. Self-contained: it sits above the page and
          releases into it; skipping or failing leaves the page exactly as it was. */}
      <IntroGate />
      <MarketingHeader />

      <main id="main" className="mx-auto w-full max-w-7xl flex-1 space-y-12 px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
        <div className="max-w-3xl">
          <p className="eyebrow">FIFA World Cup 2026 · Complete</p>
          <h1 className="mt-3 text-balance font-display text-5xl font-bold uppercase leading-[0.92] tracking-wide text-foreground sm:text-7xl">
            The World Cup, played and measured
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-fg-muted sm:text-lg">
            Every match of the 2026 tournament, the squads that played it, and a prediction model whose picks were
            fixed before kick-off and are shown here against the real results.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/tournaments">
                See the tournament
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/predict">Predict a match</Link>
            </Button>
          </div>
        </div>

        <LandingFinal />

        <nav aria-label="Sections" className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 lg:grid-cols-4">
          {SECTIONS.map((s) => (
            <Link key={s.href} href={s.href} className="group bg-surface p-5 transition-colors hover:bg-surface-2">
              <span className="flex items-center justify-between gap-2 font-display text-xl font-semibold uppercase tracking-wide text-foreground">
                {s.title}
                <ArrowRight className="h-4 w-4 shrink-0 text-fg-subtle transition-transform group-hover:translate-x-0.5 group-hover:text-primary" aria-hidden="true" />
              </span>
              <span className="mt-2 block text-sm leading-relaxed text-fg-muted">{s.body}</span>
            </Link>
          ))}
        </nav>
      </main>

      <Footer />
    </div>
  );
}
