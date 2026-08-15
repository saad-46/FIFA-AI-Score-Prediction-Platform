import type { Metadata } from "next";
import { BookmarkCheck } from "lucide-react";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { SavedPredictionsList } from "@/components/predictions/saved-predictions-list";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Prediction Archive" };

export default async function SavedPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/auth/login?redirectTo=/saved");

  return (
    <div className="space-y-8">
      <PageHeader
        icon={BookmarkCheck}
        title="Prediction Archive"
        description="Archive of simulated projections and performance evaluation logs"
      />
      <SavedPredictionsList />
    </div>
  );
}
