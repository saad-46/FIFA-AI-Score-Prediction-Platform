"use client";

import React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, getResultBg } from "@/lib/utils";
import type { TeamStats } from "@/types";

interface TeamCardProps {
  stats: TeamStats;
  rank?: number;
  delay?: number;
}

export function TeamCard({ stats, rank, delay = 0 }: TeamCardProps) {
  const winRate = (stats.win_rate * 100).toFixed(1);
  const goalDiff = stats.goal_difference;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
    >
      <Link href={`/teams/${stats.team_id}`}>
        <Card className="hover:border-emerald-500/30 hover:shadow-emerald-500/5 transition-all duration-200 cursor-pointer group">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              {rank && (
                <span className="text-lg font-black text-slate-600 w-6 text-center">
                  {rank}
                </span>
              )}
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-800 text-lg font-bold text-slate-300 flex-shrink-0">
                {stats.team_name[0]}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-200 group-hover:text-emerald-400 transition-colors truncate">
                  {stats.team_name}
                </p>
                <p className="text-xs text-slate-500">
                  {stats.matches_played} matches
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm font-bold text-slate-200">{winRate}%</p>
                <p className="text-xs text-slate-500">win rate</p>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-4 gap-2 text-center text-xs">
              <div className="rounded bg-emerald-500/10 py-1">
                <p className="font-bold text-emerald-400">{stats.wins}</p>
                <p className="text-slate-500">W</p>
              </div>
              <div className="rounded bg-amber-500/10 py-1">
                <p className="font-bold text-amber-400">{stats.draws}</p>
                <p className="text-slate-500">D</p>
              </div>
              <div className="rounded bg-red-500/10 py-1">
                <p className="font-bold text-red-400">{stats.losses}</p>
                <p className="text-slate-500">L</p>
              </div>
              <div
                className={cn(
                  "rounded py-1",
                  goalDiff > 0
                    ? "bg-emerald-500/10"
                    : goalDiff < 0
                    ? "bg-red-500/10"
                    : "bg-slate-800"
                )}
              >
                <p
                  className={cn(
                    "font-bold",
                    goalDiff > 0
                      ? "text-emerald-400"
                      : goalDiff < 0
                      ? "text-red-400"
                      : "text-slate-400"
                  )}
                >
                  {goalDiff > 0 ? "+" : ""}
                  {goalDiff}
                </p>
                <p className="text-slate-500">GD</p>
              </div>
            </div>

            {/* Form */}
            {stats.form && stats.form.length > 0 && (
              <div className="mt-3 flex items-center gap-1">
                <span className="text-xs text-slate-500 mr-1">Form:</span>
                {stats.form.slice(-5).map((result, i) => (
                  <span
                    key={i}
                    className={cn(
                      "inline-flex h-5 w-5 items-center justify-center rounded text-xs font-bold border",
                      getResultBg(result)
                    )}
                  >
                    {result}
                  </span>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  );
}
