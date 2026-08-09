"use client";

import { TrendingUp } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ProbabilityBar } from "@/components/ui/probability-bar";

interface WinProbabilityCardProps {
  homeTeam: string;
  awayTeam: string;
  homeWinProbability: number;
  drawProbability: number;
  awayWinProbability: number;
}

// CSS custom properties, not literal hex — so this matches whichever theme
// (light/dark) is active, unlike a fixed hex value would.
const TONE_VAR = { win: "var(--win)", draw: "var(--draw)", loss: "var(--loss)" } as const;

export function WinProbabilityCard({
  homeTeam,
  awayTeam,
  homeWinProbability,
  drawProbability,
  awayWinProbability,
}: WinProbabilityCardProps) {
  const data = [
    { name: homeTeam, value: Math.round(homeWinProbability * 100), color: TONE_VAR.win },
    { name: "Draw", value: Math.round(drawProbability * 100), color: TONE_VAR.draw },
    { name: awayTeam, value: Math.round(awayWinProbability * 100), color: TONE_VAR.loss },
  ];

  return (
    <Card>
      <CardHeader className="pb-2 border-b border-border/20">
        <CardTitle className="flex items-center gap-2 font-mono text-xs tracking-wider uppercase text-foreground">
          <TrendingUp className="h-4.5 w-4.5 text-primary" aria-hidden="true" />
          Outcome Probability Vector
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4">
          <div className="h-40 w-40 shrink-0" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={data} cx="50%" cy="50%" innerRadius={40} outerRadius={65} paddingAngle={2} dataKey="value">
                  {data.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: "8px",
                    color: "var(--foreground)",
                  }}
                  formatter={(value) => [`${value as number}%`, ""]}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex-1 space-y-3">
            <ProbabilityBar label={homeTeam} value={homeWinProbability} tone="win" />
            <ProbabilityBar label="Draw" value={drawProbability} tone="draw" />
            <ProbabilityBar label={awayTeam} value={awayWinProbability} tone="loss" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
