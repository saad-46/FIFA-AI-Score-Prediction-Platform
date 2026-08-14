import Link from "next/link";
import { Trophy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";

/** Distinct from Navbar (app shell) — marketing visitors are logged out by
 * definition, so this shows sign-in/sign-up CTAs instead of nav links + avatar. */
export function MarketingHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded border border-border bg-surface-2/80 shadow-lg shadow-cyan-500/5">
            <svg className="h-4.5 w-4.5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
              <path d="M2 12h20" />
            </svg>
          </div>
          <span className="text-sm font-bold tracking-[0.15em] text-foreground font-mono uppercase">
            FIFA // <span className="text-primary">INTELLIGENCE</span>
          </span>
        </Link>
        {/* No account CTAs — the platform is open. The primary action is to
            go straight into the tournament rather than to sign up. */}
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button size="sm" asChild>
            <Link href="/tournaments">Explore WC2026</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
