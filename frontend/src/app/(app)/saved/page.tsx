import type { Metadata } from "next";
import { BookmarkCheck } from "lucide-react";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { SavedPredictionsList } from "@/components/predictions/saved-predictions-list";

export const metadata: Metadata = { title: "Saved Predictions" };

export default async function SavedPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/auth/login?redirectTo=/saved");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
          <BookmarkCheck className="h-6 w-6 text-primary" aria-hidden="true" />
          Saved Predictions
        </h1>
        <p className="mt-1 text-sm text-fg-muted">Your prediction history and accuracy tracking</p>
      </div>
      <SavedPredictionsList />
    </div>
  );
}
