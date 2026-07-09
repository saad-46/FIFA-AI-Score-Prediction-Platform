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
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500">
            <Trophy className="h-4 w-4 text-white" aria-hidden="true" />
          </div>
          <span className="text-lg font-bold text-foreground">
            FIFA<span className="text-primary">AI</span>
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button variant="ghost" size="sm" asChild>
            <Link href="/auth/login">Sign in</Link>
          </Button>
          <Button size="sm" variant="gradient" asChild>
            <Link href="/auth/register">Get started free</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
