import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";

/** Distinct from Navbar (app shell) — marketing visitors are logged out by
 * definition, so this shows sign-in/sign-up CTAs instead of nav links + avatar. */
export function MarketingHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-2.5 rounded" aria-label="FIFA 26 Intelligence — home">
          <svg className="h-7 w-7 text-primary" viewBox="0 0 28 28" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
            <rect x="1.5" y="4.5" width="25" height="19" rx="2.5" />
            <path d="M14 4.5v19" />
            <circle cx="14" cy="14" r="4.25" />
          </svg>
          <span className="font-display text-xl font-bold uppercase leading-none tracking-wider text-foreground">
            FIFA 26 <span className="text-primary">Intelligence</span>
          </span>
        </Link>
        {/* No account CTAs — the platform is open. The primary action is to
            go straight into the tournament rather than to sign up. */}
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button size="sm" asChild>
            <Link href="/dashboard">Open the app</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
