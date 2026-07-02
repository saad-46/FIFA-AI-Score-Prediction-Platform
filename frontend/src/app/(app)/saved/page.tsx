import type { Metadata } from "next";
import { BookmarkCheck, Brain } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export const metadata: Metadata = { title: "Saved Predictions" };

export default async function SavedPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/auth/login?redirectTo=/saved");

  const { data: predictions } = await supabase
    .from("saved_predictions")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false })
    .limit(50);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <BookmarkCheck className="h-6 w-6 text-emerald-400" />
          Saved Predictions
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Your prediction history and accuracy tracking
        </p>
      </div>

      {predictions && predictions.length > 0 ? (
        <div className="space-y-3">
          {predictions.map((pred) => (
            <Card key={pred.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="text-center">
                      <p className="font-semibold text-slate-200">
                        {pred.home_team}
                      </p>
                    </div>
                    <div className="text-center">
                      <p className="text-xl font-black text-white">
                        {pred.predicted_home_score} — {pred.predicted_away_score}
                      </p>
                      <p className="text-xs text-slate-500">predicted</p>
                    </div>
                    <div className="text-center">
                      <p className="font-semibold text-slate-200">
                        {pred.away_team}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-emerald-400">
                      {(pred.home_win_probability * 100).toFixed(0)}% home win
                    </p>
                    <p className="text-xs text-slate-500">
                      {new Date(pred.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Brain className="h-12 w-12 text-slate-700 mb-4" />
            <p className="text-slate-400 font-medium">No saved predictions</p>
            <p className="text-slate-600 text-sm mt-1">
              Make predictions and save them to track accuracy
            </p>
            <Button className="mt-4" asChild>
              <Link href="/predict">Make a prediction</Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
