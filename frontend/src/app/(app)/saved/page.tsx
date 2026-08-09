import type { Metadata } from "next";
import { BookmarkCheck } from "lucide-react";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { SavedPredictionsList } from "@/components/predictions/saved-predictions-list";

export const metadata: Metadata = { title: "Prediction Archive" };

export default async function SavedPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/auth/login?redirectTo=/saved");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-foreground font-mono uppercase">
          <BookmarkCheck className="h-6 w-6 text-primary" aria-hidden="true" />
          Prediction Archive
        </h1>
        <p className="mt-1 text-sm text-fg-muted">Archive of simulated projections and performance evaluation logs</p>
      </div>
      <SavedPredictionsList />
    </div>
  );
}
