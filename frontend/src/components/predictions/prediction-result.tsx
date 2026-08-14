"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { BookmarkPlus, CheckCircle, Loader2, AlertTriangle, Info, TrendingUp, FileText, Lock } from "lucide-react";
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
import { TeamFlag } from "@/components/football/team-flag";
import type { PredictionResult } from "@/types";

interface PredictionResultCardProps {
  result: PredictionResult;
  isAuthenticated: boolean;
}

const INSIGHT_STYLE = {
  advantage: { icon: TrendingUp, className: "text-win bg-win/5 border-win/20" },
  warning: { icon: AlertTriangle, className: "text-draw bg-draw/5 border-draw/20" },
  neutral: { icon: Info, className: "text-primary bg-primary/5 border-primary/20" },
} as const;

export function PredictionResultCard({ result, isAuthenticated }: PredictionResultCardProps) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    if (!isAuthenticated) {
      toast({
        title: "Sign In Required",
        description: "Authenticate to persist predictions within your dashboard directory.",
        variant: "destructive",
      });
      return;
    }
    setSaving(true);
    try {
      await predictionsApi.save(result.prediction_id);
      setSaved(true);
      toast({ title: "Dossier Saved", description: "Prediction saved to database registry.", variant: "success" });
    } catch (err) {
      toast({ title: "Save Failed", description: getApiErrorMessage(err), variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const confidenceColor =
    result.confidence_score >= 0.7 ? "text-win" : result.confidence_score >= 0.5 ? "text-primary" : "text-loss";

  // Calculate high-level summary outcome
  const getVerdict = () => {
    const homeProb = result.home_win_probability;
    const awayProb = result.away_win_probability;
    const drawProb = result.draw_probability;
    
    if (Math.abs(homeProb - awayProb) < 0.05) {
      return `STOCHASTIC EQUILIBRIUM (DRAW OUTLOOK)`;
    }
    return homeProb > awayProb 
      ? `${result.home_team.toUpperCase()} OUTCOME ADVANTAGE` 
      : `${result.away_team.toUpperCase()} OUTCOME ADVANTAGE`;
  };

  return (
    <div className="space-y-6">
      {/* SECTION 1: EXECUTIVE VERDICT (Immediate Reveal) */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <Card className="border-border/60 bg-black/40 backdrop-blur-md shadow-2xl overflow-hidden relative">
          <div className="absolute top-0 right-0 w-[120px] h-[120px] bg-cyan-500/5 blur-[30px] rounded-full pointer-events-none" />
          
          <CardHeader className="pb-3 border-b border-border/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.2em] text-zinc-500 uppercase">
                <FileText className="h-3.5 w-3.5 text-primary" />
                INTELLIGENCE DOSSIER // SECURE_REPORT
              </div>
              
              <div className="flex items-center gap-3">
                <span className={cn("font-mono text-xs font-bold", confidenceColor)}>
                  {formatPercent(result.confidence_score)} CONFIDENCE
                </span>
                <Button 
                  size="sm" 
                  variant={saved ? "secondary" : "outline"} 
                  onClick={handleSave} 
                  disabled={saving || saved}
                  className="font-mono text-[10px] uppercase tracking-wider h-8"
                >
                  {saving ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : saved ? (
                    <CheckCircle className="h-3 w-3 text-win" />
                  ) : (
                    <BookmarkPlus className="h-3 w-3" />
                  )}
                  {saved ? "Archived" : "Archive"}
                </Button>
              </div>
            </div>
          </CardHeader>
          
          <CardContent className="pt-6 space-y-6">
            {/* Target Verdict */}
            <div className="text-center space-y-1">
              <span className="text-[10px] font-mono tracking-widest text-zinc-500 uppercase">Prototypal Outturn Verdict</span>
              <h2 className="text-lg md:text-xl font-bold font-mono tracking-wide text-foreground">
                {getVerdict()}
              </h2>
            </div>

            {/* Score Projection Display */}
            <div className="flex items-center justify-center gap-8 py-4 border-y border-border/20 bg-zinc-950/25 rounded-lg">
              <div className="text-center w-24">
                <TeamFlag name={result.home_team} size="lg" className="mr-1.5 inline-block align-middle" />
                <p className="text-[10px] font-mono font-bold tracking-wider text-zinc-400 mt-1 truncate">{result.home_team}</p>
                <motion.span
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: 0.2, type: "spring" }}
                  className="block font-mono text-5xl font-black text-foreground mt-2"
                >
                  {result.predicted_home_score}
                </motion.span>
              </div>
              <div className="text-center font-mono text-zinc-600 text-2xl font-bold">
                :
              </div>
              <div className="text-center w-24">
                <TeamFlag name={result.away_team} size="lg" className="ml-1.5 inline-block align-middle" />
                <p className="text-[10px] font-mono font-bold tracking-wider text-zinc-400 mt-1 truncate">{result.away_team}</p>
                <motion.span
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: 0.3, type: "spring" }}
                  className="block font-mono text-5xl font-black text-foreground mt-2"
                >
                  {result.predicted_away_score}
                </motion.span>
              </div>
            </div>

            {/* Sub-Metrics details */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-surface/30 p-2.5 rounded text-center border border-border/10">
                <span className="block text-[9px] font-mono text-fg-muted uppercase">Home xG</span>
                <span className="block font-mono text-sm font-bold text-cyan-400 mt-0.5">{formatGoals(result.expected_home_goals)}</span>
              </div>
              <div className="bg-surface/30 p-2.5 rounded text-center border border-border/10">
                <span className="block text-[9px] font-mono text-fg-muted uppercase">Away xG</span>
                <span className="block font-mono text-sm font-bold text-cyan-400 mt-0.5">{formatGoals(result.expected_away_goals)}</span>
              </div>
              <div className="bg-surface/30 p-2.5 rounded text-center border border-border/10">
                <span className="block text-[9px] font-mono text-fg-muted uppercase">Distribution</span>
                <span className="block font-mono text-xs font-bold text-foreground mt-1.5">{result.most_likely_score}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* SECTIONS 2-4: analytics. On wide screens these sit two-up rather
          than stacking — each is a self-contained chart and the old single
          column left most of the viewport empty. Collapses to one column
          below xl so nothing is cramped on tablet/mobile. */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2 xl:items-start">
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
      >
        <WinProbabilityCard
          homeTeam={result.home_team}
          awayTeam={result.away_team}
          homeWinProbability={result.home_win_probability}
          drawProbability={result.draw_probability}
          awayWinProbability={result.away_win_probability}
        />
      </motion.div>

      {/* SECTION 3: POISSON SCORELINE DISTRIBUTION (Staggered Reveal) */}
      {result.top_scorelines.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5 }}
        >
          <ScorelineDistribution scorelines={result.top_scorelines} mostLikelyScore={result.most_likely_score} />
        </motion.div>
      )}

      {/* SECTION 4: SHAP REASONING (Staggered Reveal) */}
      {result.prediction_explanation && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6, duration: 0.5 }}
        >
          <ShapExplanation explanation={result.prediction_explanation} />
        </motion.div>
      )}

      </div>

      {/* SECTION 5: TACTICAL INSIGHTS (Staggered Reveal) */}
      {result.insights && result.insights.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8, duration: 0.5 }}
        >
          <Card className="border-border/60 bg-black/40">
            <CardHeader className="pb-2 border-b border-border/20">
              <CardTitle className="flex items-center gap-2 font-mono text-xs tracking-wider uppercase text-foreground">
                <Info className="h-4 w-4 text-cyan-400" aria-hidden="true" />
                Notable Factors
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-4">
              {/* These come from the backend's rule-based checks over real
                  match history (home win rate, recent form, H2H record, xG
                  total, model confidence) — each only appears when its
                  threshold is actually met. The section used to be titled
                  "Strategic Risk Factors", which mislabelled every
                  type="advantage" entry as a risk. */}
              <p className="pb-1 text-[11px] text-fg-muted">
                Derived from historical results for this matchup — shown only when the
                underlying data supports them.
              </p>
              {result.insights.map((insight, i) => {
                const { icon: Icon, className } = INSIGHT_STYLE[insight.type];
                return (
                  <div key={i} className={cn("flex gap-3 rounded-lg border p-3 items-start", className)}>
                    <Icon className="h-4 w-4 mt-0.5 shrink-0" aria-hidden="true" />
                    <div className="space-y-0.5">
                      <p className="text-xs font-semibold font-mono tracking-wide uppercase">{insight.title}</p>
                      <p className="text-xs text-zinc-400 leading-normal">{insight.description}</p>
                    </div>
                    <Badge variant="outline" className="ml-auto shrink-0 text-[9px] font-mono uppercase tracking-wider border-current opacity-70">
                      {insight.impact} IMPACT
                    </Badge>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* SECTION 6: HISTORICAL H2H MATRIX (Staggered Reveal) */}
      {result.head_to_head && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.0, duration: 0.5 }}
        >
          <HeadToHeadCard stats={result.head_to_head} homeTeam={result.home_team} awayTeam={result.away_team} />
        </motion.div>
      )}

      {/* Footer Info */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.5 }}
        transition={{ delay: 1.2 }}
        className="text-center font-mono text-[9px] tracking-widest text-zinc-600 uppercase"
      >
        Calculation version {result.model_version} · RUN_ID: {result.prediction_id.slice(0, 8)}
      </motion.p>
    </div>
  );
}
