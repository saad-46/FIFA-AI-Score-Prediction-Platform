"use client";

import React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { PerformanceTrendPoint } from "@/types";

interface WinProbabilityChartProps {
  data: PerformanceTrendPoint[];
  teamName: string;
}

const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded border border-border bg-surface/90 backdrop-blur-md p-3 shadow-2xl text-xs font-mono">
      <p className="font-semibold text-foreground mb-2">{label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 mt-1">
          <div
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-fg-muted uppercase tracking-wider">{entry.name}:</span>
          <span className="font-bold text-foreground">{entry.value}</span>
        </div>
      ))}
    </div>
  );
};

export function WinProbabilityChart({
  data,
  teamName,
}: WinProbabilityChartProps) {
  return (
    <Card>
      <CardHeader className="pb-2 border-b border-border/20">
        <CardTitle className="font-mono text-xs tracking-wider uppercase text-foreground">
          {teamName} // Historical Performance Vector
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6">
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="winsGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="drawsGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#475569" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#475569" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="lossesGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.4} />
            <XAxis
              dataKey="date"
              tick={{ fill: "var(--fg-muted)", fontSize: 10, fontFamily: "monospace" }}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "var(--fg-muted)", fontSize: 10, fontFamily: "monospace" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: "10px", fontFamily: "monospace", color: "var(--fg-muted)", textTransform: "uppercase", letterSpacing: "1px" }}
            />
            <Area
              type="monotone"
              dataKey="wins"
              name="Wins"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#winsGrad)"
            />
            <Area
              type="monotone"
              dataKey="draws"
              name="Draws"
              stroke="#475569"
              strokeWidth={2}
              fill="url(#drawsGrad)"
            />
            <Area
              type="monotone"
              dataKey="losses"
              name="Losses"
              stroke="#f43f5e"
              strokeWidth={2}
              fill="url(#lossesGrad)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
