import type { Metadata } from "next";
import { BookmarkCheck } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { SavedPredictionsList } from "@/components/predictions/saved-predictions-list";
import { PageHeader } from "@/components/layout/page-header";
import { GuestState } from "@/components/auth/guest-state";

export const metadata: Metadata = { title: "Saved Predictions" };

export default async function SavedPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Saved predictions are genuinely per-account — GET /predictions/saved
  // requires a bearer token and RLS scopes rows to auth.uid(). But that is a
  // reason to explain the situation, not to bounce the visitor to a login page
  // they never asked for. The page stays reachable and says what an account
  // would add; running predictions needs no account at all.
  return (
    <div className="space-y-8">
      <PageHeader
        icon={BookmarkCheck}
        title="Saved Predictions"
        description="Predictions you've kept, with how they scored against the real result"
      />
      {user ? (
        <SavedPredictionsList />
      ) : (
        <GuestState
          icon={BookmarkCheck}
          title="Nothing saved yet"
          description="Running predictions and simulations doesn't need an account — everything on this site is open. Sign in only if you'd like to keep predictions here and track how they scored."
          redirectTo="/saved"
          signInLabel="Sign in to save predictions"
        />
      )}
    </div>
  );
}
