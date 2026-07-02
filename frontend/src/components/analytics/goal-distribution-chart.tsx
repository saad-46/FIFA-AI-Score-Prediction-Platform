"use client";

import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
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

  return (
    <Card>
      <CardHeader>
        <CardTitle>Goal Distribution by Minute</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart
            data={data}
            margin={{ top: 5, right: 10, left: -20, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis
              dataKey="minute"
              tickFormatter={(v) => MINUTE_LABELS[v] ?? `${v}'`}
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={{ stroke: "#1e293b" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1e293b",
                border: "1px solid #334155",
                borderRadius: "8px",
                color: "#f1f5f9",
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
                      ? "#10b981"
                      : entry.goals > maxGoals * 0.7
                      ? "#34d399"
                      : "#1e3a2f"
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
