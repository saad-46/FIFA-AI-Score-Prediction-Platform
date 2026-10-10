import Link from "next/link";
import { Mail } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function VerifyEmailPage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md rounded-lg border border-border bg-surface p-8 text-center">
        <Mail className="mx-auto h-8 w-8 text-primary" aria-hidden="true" />
        <h1 className="mt-4 font-display text-3xl font-bold uppercase tracking-wide text-foreground">Check your email</h1>
        <p className="mt-3 text-sm leading-relaxed text-fg-muted">
          We sent a confirmation link to your email address. Open it to activate your account.
        </p>
        <Button variant="outline" asChild className="mt-6">
          <Link href="/auth/login">Back to sign in</Link>
        </Button>
      </div>
    </main>
  );
}
