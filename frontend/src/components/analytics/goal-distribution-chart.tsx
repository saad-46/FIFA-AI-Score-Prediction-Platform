"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { GoalDistribution } from "@/types";

interface GoalDistributionChartProps {
  data: GoalDistribution[];
}

const MINUTE_LABELS: Record<number, string> = {
  0: "1-15",
  15: "16-30",
  30: "31-45",
  45: "46-60",
  60: "61-75",
  75: "76-90",
  90: "90+",
};

export function GoalDistributionChart({ data }: GoalDistributionChartProps) {
  const maxGoals = Math.max(...data.map((d) => d.goals));
  const isSynthetic = data.some((d) => d.is_synthetic);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 border-b border-border/20">
        <CardTitle className="font-mono text-xs tracking-wider uppercase text-foreground">
          Goal Distribution Vector
        </CardTitle>
        {isSynthetic && (
          <Badge variant="synthetic" title="No goal-minute-level data exists yet — this chart uses placeholder data.">
            Sample data
          </Badge>
        )}
      </CardHeader>
      <CardContent className="pt-6">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.4} vertical={false} />
            <XAxis
              dataKey="minute"
              tickFormatter={(v) => MINUTE_LABELS[v] ?? `${v}'`}
              tick={{ fill: "var(--fg-muted)", fontSize: 10, fontFamily: "monospace" }}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={false}
            />
            <YAxis tick={{ fill: "var(--fg-muted)", fontSize: 10, fontFamily: "monospace" }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: "4px",
                color: "var(--foreground)",
                fontFamily: "monospace",
                fontSize: "11px",
              }}
              formatter={(value) => [value as number, "GOALS"]}
              labelFormatter={(label) => `INTERVAL: ${MINUTE_LABELS[label] ?? label}`}
            />
            <Bar dataKey="goals" radius={[2, 2, 0, 0]}>
              {data.map((entry, index) => (
                <Cell
                  key={index}
                  fill={
                    entry.goals === maxGoals
                      ? "var(--primary)"
                      : entry.goals > maxGoals * 0.7
                      ? "color-mix(in srgb, var(--primary) 60%, transparent)"
                      : "var(--border)"
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
