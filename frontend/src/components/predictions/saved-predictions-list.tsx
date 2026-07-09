"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { Bookmark, Brain, Trash2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { ListSkeleton } from "@/components/ui/page-skeletons";
import { predictionsApi } from "@/lib/api/predictions";
import { getApiErrorMessage } from "@/lib/api/client";
import { toast } from "@/hooks/use-toast";
import { formatPercent } from "@/lib/utils";
import type { SavedPrediction } from "@/types";

export function SavedPredictionsList() {
  const {
    data: predictions,
    error,
    isLoading,
    mutate,
  } = useSWR<SavedPrediction[]>("saved-predictions", () => predictionsApi.getSaved());
  const { data: accuracy } = useSWR("prediction-accuracy", () => predictionsApi.getAccuracyStats());
  const [pendingDelete, setPendingDelete] = useState<SavedPrediction | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await predictionsApi.deleteSaved(pendingDelete.id);
      toast({ title: "Deleted", description: "Prediction removed." });
      setPendingDelete(null);
      mutate();
    } catch (err) {
      toast({ title: "Error", description: getApiErrorMessage(err), variant: "destructive" });
    } finally {
      setDeleting(false);
    }
  };

  if (isLoading) return <ListSkeleton count={5} />;

  if (error) {
    return (
      <ErrorState
        title="Couldn't load saved predictions"
        description={getApiErrorMessage(error)}
        onRetry={() => mutate()}
      />
    );
  }

  if (!predictions || predictions.length === 0) {
    return (
      <Card>
        <CardContent>
          <EmptyState
            icon={Brain}
            title="No saved predictions"
            description="Make a prediction and save it to track its accuracy here."
            action={
              <Button asChild>
                <Link href="/predict">Make a prediction</Link>
              </Button>
            }
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {accuracy && accuracy.total > 0 && (
        <Card>
          <CardContent className="flex items-center justify-between p-5">
            <div>
              <p className="text-sm text-fg-muted">Accuracy so far</p>
              <p className="font-mono text-2xl font-bold text-foreground">
                {formatPercent(accuracy.accuracy)}
              </p>
            </div>
            <p className="text-sm text-fg-muted">
              {accuracy.correct} / {accuracy.total} correct
            </p>
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {predictions.map((pred) => (
          <Card key={pred.id}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between gap-4">
                <div className="flex flex-1 items-center gap-4 min-w-0">
                  <p className="flex-1 truncate text-right font-semibold text-foreground">
                    {pred.home_team}
                  </p>
                  <div className="text-center shrink-0">
                    <p className="font-mono text-xl font-black text-foreground">
                      {pred.predicted_home_score} – {pred.predicted_away_score}
                    </p>
                    {pred.was_correct !== null && pred.was_correct !== undefined && (
                      <Badge variant={pred.was_correct ? "win" : "loss"} className="mt-1">
                        {pred.was_correct ? "Correct" : "Incorrect"}
                      </Badge>
                    )}
                  </div>
                  <p className="flex-1 truncate text-left font-semibold text-foreground">
                    {pred.away_team}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <div className="text-right">
                    <p className="text-sm font-medium text-win">
                      {formatPercent(pred.home_win_probability)} home win
                    </p>
                    <p className="text-xs text-fg-muted">
                      {new Date(pred.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Delete prediction for ${pred.home_team} vs ${pred.away_team}`}
                    onClick={() => setPendingDelete(pred)}
                  >
                    <Trash2 className="h-4 w-4 text-loss" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={!!pendingDelete} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Bookmark className="h-4 w-4" aria-hidden="true" />
              Delete this prediction?
            </DialogTitle>
            <DialogDescription>
              {pendingDelete && `${pendingDelete.home_team} vs ${pendingDelete.away_team} will be removed. This can't be undone.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button variant="destructive" loading={deleting} onClick={handleDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
