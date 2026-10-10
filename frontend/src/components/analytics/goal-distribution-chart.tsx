"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

  // The API marks this series as synthetic when the database holds no
  // goal-minute events, which is the case today. A bar chart of placeholder
  // numbers looks exactly like a real finding, and a small "sample data" badge
  // in the corner does not undo that -- so the placeholder is not drawn at all.
  // When real goal-minute data exists the flag clears and the chart appears.
  if (isSynthetic) {
    return (
      <div className="rounded-lg border border-dashed border-border px-5 py-10 text-center">
        <p className="font-display text-xl font-semibold uppercase tracking-wide text-fg-muted">
          Goal timing is not available
        </p>
        <p className="mx-auto mt-1.5 max-w-md text-sm leading-relaxed text-fg-subtle">
          The match record holds final scores but not the minute each goal was scored, so there is nothing real to
          chart here yet.
        </p>
      </div>
    );
  }

  return (
    <Card>
      <CardHeader className="border-b border-border pb-3">
        <CardTitle className="font-display text-lg font-semibold uppercase tracking-wide text-foreground">
          Goals by period of the match
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.4} vertical={false} />
            <XAxis
              dataKey="minute"
              tickFormatter={(v) => MINUTE_LABELS[v] ?? `${v}'`}
              tick={{ fill: "var(--fg-muted)", fontSize: 10 }}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={false}
            />
            <YAxis tick={{ fill: "var(--fg-muted)", fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: "4px",
                color: "var(--foreground)",
                fontSize: "12px",
              }}
              formatter={(value) => [value as number, "Goals"]}
              labelFormatter={(label) => `Minutes ${MINUTE_LABELS[label] ?? label}`}
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
