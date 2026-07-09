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
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle>Goal Distribution by Minute</CardTitle>
        {isSynthetic && (
          <Badge variant="synthetic" title="No goal-minute-level data exists yet — this chart uses placeholder data.">
            Sample data
          </Badge>
        )}
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="minute"
              tickFormatter={(v) => MINUTE_LABELS[v] ?? `${v}'`}
              tick={{ fill: "var(--fg-muted)", fontSize: 11 }}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={false}
            />
            <YAxis tick={{ fill: "var(--fg-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: "8px",
                color: "var(--foreground)",
              }}
              formatter={(value) => [value as number, "Goals"]}
              labelFormatter={(label) => `Minute: ${MINUTE_LABELS[label] ?? label}`}
            />
            <Bar dataKey="goals" radius={[4, 4, 0, 0]}>
              {data.map((entry, index) => (
                <Cell
                  key={index}
                  fill={
                    entry.goals === maxGoals
                      ? "var(--win)"
                      : entry.goals > maxGoals * 0.7
                      ? "var(--accent)"
                      : "var(--surface-2)"
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
