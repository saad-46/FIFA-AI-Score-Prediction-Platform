import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

interface GuestStateProps {
  icon: LucideIcon;
  title: string;
  /** What the visitor can do right now, without an account. Lead with this —
   * the account is the optional part. */
  description: string;
  /** Where to send someone who does want an account, with the return path. */
  redirectTo: string;
  signInLabel?: string;
  /** Show the secondary "create account" action. Off by default: most guest
   * states only need one quiet way in. */
  showCreateAccount?: boolean;
}

/**
 * The state an account-backed page shows to a visitor who isn't signed in.
 *
 * Deliberately not a login wall. The product is usable anonymously, so these
 * pages stay reachable and explain what an account would add rather than
 * demanding one — the sign-in action is present but secondary, and nothing
 * here fabricates data the visitor doesn't have.
 */
export function GuestState({
  icon: Icon,
  title,
  description,
  redirectTo,
  signInLabel = "Sign in",
  showCreateAccount = false,
}: GuestStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/60 bg-surface/30 px-6 py-14 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-surface-2/60">
        <Icon className="h-5 w-5 text-primary" aria-hidden="true" />
      </span>
      <h2 className="pt-4 font-mono text-sm uppercase tracking-wider text-foreground">{title}</h2>
      <p className="max-w-md pt-2 text-sm leading-relaxed text-fg-muted">{description}</p>
      <div className="flex flex-wrap items-center justify-center gap-2 pt-5">
        <Button variant="outline" size="sm" asChild>
          <Link href={`/auth/login?redirectTo=${encodeURIComponent(redirectTo)}`}>
            {signInLabel}
          </Link>
        </Button>
        {showCreateAccount && (
          <Button variant="ghost" size="sm" asChild>
            <Link href={`/auth/register?redirectTo=${encodeURIComponent(redirectTo)}`}>
              Create account
            </Link>
          </Button>
        )}
      </div>
    </div>
  );
}
