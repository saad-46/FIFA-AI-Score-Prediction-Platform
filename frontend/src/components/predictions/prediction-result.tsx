"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { BookmarkPlus, CheckCircle, Loader2, AlertTriangle, Info, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { predictionsApi } from "@/lib/api/predictions";
import { getApiErrorMessage } from "@/lib/api/client";
import { toast } from "@/hooks/use-toast";
import { formatPercent, formatGoals, cn } from "@/lib/utils";
import { WinProbabilityCard } from "@/components/football/win-probability-card";
import { ScorelineDistribution } from "@/components/football/scoreline-distribution";
import { ShapExplanation } from "@/components/football/shap-explanation";
import { HeadToHeadCard } from "@/components/football/head-to-head-card";
import type { PredictionResult } from "@/types";

interface PredictionResultCardProps {
  result: PredictionResult;
  isAuthenticated: boolean;
}

const INSIGHT_STYLE = {
  advantage: { icon: TrendingUp, className: "text-win bg-win/10 border-win/20" },
  warning: { icon: AlertTriangle, className: "text-draw bg-draw/10 border-draw/20" },
  neutral: { icon: Info, className: "text-accent bg-accent/10 border-accent/20" },
} as const;

export function PredictionResultCard({ result, isAuthenticated }: PredictionResultCardProps) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    if (!isAuthenticated) {
      toast({
        title: "Sign in required",
        description: "Create an account to save predictions.",
        variant: "destructive",
      });
      return;
    }
    setSaving(true);
    try {
      await predictionsApi.save(result.prediction_id);
      setSaved(true);
      toast({ title: "Saved!", description: "Prediction saved to your account.", variant: "success" });
    } catch (err) {
      toast({ title: "Error", description: getApiErrorMessage(err), variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const confidenceColor =
    result.confidence_score >= 0.7 ? "text-win" : result.confidence_score >= 0.5 ? "text-draw" : "text-loss";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-4"
    >
      {/* Score prediction */}
      <Card glow>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle>Predicted Score</CardTitle>
            <div className="flex items-center gap-2">
              <span className={cn("text-sm font-medium", confidenceColor)}>
                {formatPercent(result.confidence_score)} confidence
              </span>
              <Button size="sm" variant={saved ? "secondary" : "default"} onClick={handleSave} disabled={saving || saved}>
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : saved ? (
                  <CheckCircle className="h-4 w-4 text-win" />
                ) : (
                  <BookmarkPlus className="h-4 w-4" />
                )}
                {saved ? "Saved" : "Save"}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center gap-8 py-6">
            <div className="text-center">
              <p className="text-sm font-medium text-fg-muted mb-2">{result.home_team}</p>
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", delay: 0.2 }}
                className="font-mono text-6xl font-black text-foreground"
              >
                {result.predicted_home_score}
              </motion.span>
            </div>
            <div className="text-center">
              <span className="text-3xl font-bold text-fg-muted">—</span>
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-fg-muted mb-2">{result.away_team}</p>
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", delay: 0.3 }}
                className="font-mono text-6xl font-black text-foreground"
              >
                {result.predicted_away_score}
              </motion.span>
            </div>
          </div>
          {result.most_likely_score && (
            <p className="text-center text-xs text-fg-muted -mt-2 mb-2">
              Most likely scoreline: <span className="font-mono font-semibold text-foreground">{result.most_likely_score}</span>
            </p>
          )}

          <div className="grid grid-cols-2 gap-4 mt-2">
            <div className="rounded-lg bg-surface-2/50 p-3 text-center">
              <p className="text-xs text-fg-muted mb-1">xG {result.home_team}</p>
              <p className="font-mono text-xl font-bold text-accent">{formatGoals(result.expected_home_goals)}</p>
            </div>
            <div className="rounded-lg bg-surface-2/50 p-3 text-center">
              <p className="text-xs text-fg-muted mb-1">xG {result.away_team}</p>
              <p className="font-mono text-xl font-bold text-accent">{formatGoals(result.expected_away_goals)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <WinProbabilityCard
        homeTeam={result.home_team}
        awayTeam={result.away_team}
        homeWinProbability={result.home_win_probability}
        drawProbability={result.draw_probability}
        awayWinProbability={result.away_win_probability}
      />

      {result.top_scorelines.length > 0 && (
        <ScorelineDistribution scorelines={result.top_scorelines} mostLikelyScore={result.most_likely_score} />
      )}

      {result.prediction_explanation && <ShapExplanation explanation={result.prediction_explanation} />}

      {result.insights && result.insights.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2">
              <Info className="h-4 w-4 text-draw" aria-hidden="true" />
              AI Insights
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {result.insights.map((insight, i) => {
              const { icon: Icon, className } = INSIGHT_STYLE[insight.type];
              return (
                <div key={i} className={cn("flex gap-3 rounded-lg border p-3", className)}>
                  <Icon className="h-4 w-4 mt-0.5 shrink-0" aria-hidden="true" />
                  <div>
                    <p className="text-sm font-medium">{insight.title}</p>
                    <p className="text-xs opacity-80 mt-0.5">{insight.description}</p>
                  </div>
                  <Badge variant="outline" className="ml-auto self-start text-xs border-current opacity-60">
                    {insight.impact}
                  </Badge>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {result.head_to_head && (
        <HeadToHeadCard stats={result.head_to_head} homeTeam={result.home_team} awayTeam={result.away_team} />
      )}

      <p className="text-center text-xs text-fg-muted/60">
        Model v{result.model_version} · Prediction ID: {result.prediction_id}
      </p>
    </motion.div>
  );
}
