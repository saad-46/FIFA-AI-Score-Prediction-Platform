"use client";

import React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Calendar, MapPin } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import type { Match } from "@/types";

interface MatchCardProps {
  match: Match;
  delay?: number;
}

export function MatchCard({ match, delay = 0 }: MatchCardProps) {
  const isCompleted = match.status === "completed";
  const isLive = match.status === "live";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay }}
    >
      <Link href={`/matches/${match.id}`}>
        <Card className="hover:border-slate-600 transition-all duration-200 cursor-pointer group">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Calendar className="h-3.5 w-3.5" />
                {formatDate(match.date)}
                {match.city && (
                  <>
                    <MapPin className="h-3.5 w-3.5 ml-1" />
                    {match.city}
                  </>
                )}
              </div>
              <div className="flex items-center gap-2">
                {isLive && <Badge variant="live">LIVE</Badge>}
                <Badge variant="secondary" className="text-xs">
                  {match.tournament}
                </Badge>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex-1 text-right">
                <p className="font-semibold text-slate-200 group-hover:text-emerald-400 transition-colors">
                  {match.home_team.name}
                </p>
                <p className="text-xs text-slate-500">{match.home_team.country}</p>
              </div>

              <div className="mx-4 text-center min-w-[80px]">
                {isCompleted ? (
                  <div className="flex items-center justify-center gap-2">
                    <span className="text-2xl font-black text-white">
                      {match.home_score}
                    </span>
                    <span className="text-slate-500">—</span>
                    <span className="text-2xl font-black text-white">
                      {match.away_score}
                    </span>
                  </div>
                ) : isLive ? (
                  <div className="flex items-center justify-center gap-2">
                    <span className="text-2xl font-black text-red-400">
                      {match.home_score ?? 0}
                    </span>
                    <span className="text-red-500 animate-pulse">•</span>
                    <span className="text-2xl font-black text-red-400">
                      {match.away_score ?? 0}
                    </span>
                  </div>
                ) : (
                  <span className="text-sm font-medium text-slate-500">vs</span>
                )}
                {match.stage && (
                  <p className="text-xs text-slate-600 mt-0.5">{match.stage}</p>
                )}
              </div>

              <div className="flex-1 text-left">
                <p className="font-semibold text-slate-200 group-hover:text-emerald-400 transition-colors">
                  {match.away_team.name}
                </p>
                <p className="text-xs text-slate-500">{match.away_team.country}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  );
}
