"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  BookmarkPlus,
  CheckCircle,
  Loader2,
  TrendingUp,
  Target,
  Zap,
  AlertTriangle,
  Info,
  Shield,
} from "lucide-react";
import {
  RadialBarChart,
  RadialBar,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { predictionsApi } from "@/lib/api/predictions";
import { toast } from "@/hooks/use-toast";
import { formatPercent, formatGoals, cn } from "@/lib/utils";
import type { PredictionResult } from "@/types";

interface PredictionResultCardProps {
  result: PredictionResult;
  isAuthenticated: boolean;
}

const WIN_COLORS = ["#10b981", "#f59e0b", "#ef4444"];

export function PredictionResultCard({
  result,
  isAuthenticated,
}: PredictionResultCardProps) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const winData = [
    {
      name: result.home_team,
      value: Math.round(result.home_win_probability * 100),
      color: "#10b981",
    },
    {
      name: "Draw",
      value: Math.round(result.draw_probability * 100),
      color: "#f59e0b",
    },
    {
      name: result.away_team,
      value: Math.round(result.away_win_probability * 100),
      color: "#ef4444",
    },
  ];

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
      toast({ title: "Saved!", description: "Prediction saved to your account.", variant: "success" as never });
    } catch {
      toast({ title: "Error", description: "Could not save prediction.", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const confidenceColor =
    result.confidence_score >= 0.7
      ? "text-emerald-400"
      : result.confidence_score >= 0.5
      ? "text-amber-400"
      : "text-red-400";

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
              <Button
                size="sm"
                variant={saved ? "secondary" : "default"}
                onClick={handleSave}
                disabled={saving || saved}
              >
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : saved ? (
                  <CheckCircle className="h-4 w-4 text-emerald-400" />
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
              <p className="text-sm font-medium text-slate-400 mb-2">
                {result.home_team}
              </p>
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", delay: 0.2 }}
                className="text-6xl font-black text-white"
              >
                {result.predicted_home_score}
              </motion.span>
            </div>
            <div className="text-center">
              <span className="text-3xl font-bold text-slate-500">—</span>
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-slate-400 mb-2">
                {result.away_team}
              </p>
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", delay: 0.3 }}
                className="text-6xl font-black text-white"
              >
                {result.predicted_away_score}
              </motion.span>
            </div>
          </div>

          {/* Expected goals */}
          <div className="grid grid-cols-2 gap-4 mt-2">
            <div className="rounded-lg bg-slate-800/50 p-3 text-center">
              <p className="text-xs text-slate-500 mb-1">xG {result.home_team}</p>
              <p className="text-xl font-bold text-cyan-400">
                {formatGoals(result.home_expected_goals)}
              </p>
            </div>
            <div className="rounded-lg bg-slate-800/50 p-3 text-center">
              <p className="text-xs text-slate-500 mb-1">xG {result.away_team}</p>
              <p className="text-xl font-bold text-cyan-400">
                {formatGoals(result.away_expected_goals)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Win probability */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-emerald-400" />
            Win Probability
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="h-40 w-40 flex-shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={winData}
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={65}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {winData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1e293b",
                      border: "1px solid #334155",
                      borderRadius: "8px",
                      color: "#f1f5f9",
                    }}
                    formatter={(value) => [`${value as number}%`, ""]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1 space-y-3">
              {winData.map((item, i) => (
                <div key={i} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-300">{item.name}</span>
                    <span className="font-semibold" style={{ color: item.color }}>
                      {item.value}%
                    </span>
                  </div>
                  <Progress
                    value={item.value}
                    className="h-1.5"
                    indicatorClassName={
                      i === 0
                        ? "bg-emerald-500"
                        : i === 1
                        ? "bg-amber-500"
                        : "bg-red-500"
                    }
                  />
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* AI Insights */}
      {result.insights && result.insights.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-amber-400" />
              AI Insights
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {result.insights.map((insight, i) => {
              const Icon =
                insight.type === "advantage"
                  ? TrendingUp
                  : insight.type === "warning"
                  ? AlertTriangle
                  : Info;
              const color =
                insight.type === "advantage"
                  ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                  : insight.type === "warning"
                  ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
                  : "text-blue-400 bg-blue-500/10 border-blue-500/20";
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className={cn(
                    "flex gap-3 rounded-lg border p-3",
                    color
                  )}
                >
                  <Icon className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium">{insight.title}</p>
                    <p className="text-xs opacity-80 mt-0.5">
                      {insight.description}
                    </p>
                  </div>
                  <Badge
                    variant="outline"
                    className="ml-auto self-start text-xs border-current opacity-60"
                  >
                    {insight.impact}
                  </Badge>
                </motion.div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Head to head */}
      {result.head_to_head && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-cyan-400" />
              Head to Head
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold text-emerald-400">
                  {result.head_to_head.home_team_wins}
                </p>
                <p className="text-xs text-slate-500 mt-1">{result.home_team} wins</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-amber-400">
                  {result.head_to_head.draws}
                </p>
                <p className="text-xs text-slate-500 mt-1">Draws</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-red-400">
                  {result.head_to_head.away_team_wins}
                </p>
                <p className="text-xs text-slate-500 mt-1">{result.away_team} wins</p>
              </div>
            </div>
            <Separator className="my-4" />
            <div className="grid grid-cols-2 gap-4 text-center text-sm">
              <div>
                <p className="text-slate-400">Total matches</p>
                <p className="font-semibold text-slate-200">
                  {result.head_to_head.total_matches}
                </p>
              </div>
              <div>
                <p className="text-slate-400">Goals</p>
                <p className="font-semibold text-slate-200">
                  {result.head_to_head.home_team_goals} –{" "}
                  {result.head_to_head.away_team_goals}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <p className="text-center text-xs text-slate-600">
        Model v{result.model_version} · Prediction ID: {result.prediction_id}
      </p>
    </motion.div>
  );
}
