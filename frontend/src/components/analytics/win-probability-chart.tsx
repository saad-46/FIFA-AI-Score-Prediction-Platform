"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PerformanceTrendPoint } from "@/types";

interface WinProbabilityChartProps {
  data: PerformanceTrendPoint[];
  teamName: string;
}

/** "2026-07" -> "Jul 26" */
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function monthLabel(value: string): string {
  const [year, month] = value.split("-").map(Number);
  if (!year || !month) return value;
  return `${MONTHS[month - 1]} ${String(year).slice(2)}`;
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((sum, p) => sum + (p.value ?? 0), 0);
  return (
    <div className="rounded-md border border-border-strong bg-surface p-3 text-xs shadow-xl">
      <p className="mb-1.5 font-semibold text-foreground">
        {label ? monthLabel(label) : ""} · {total} {total === 1 ? "match" : "matches"}
      </p>
      {payload.map((entry) => (
        <p key={entry.name} className="flex items-center gap-2 text-fg-muted">
          <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: entry.color }} aria-hidden="true" />
          {entry.name}
          <span className="tabular ml-auto pl-4 font-semibold text-foreground">{entry.value}</span>
        </p>
      ))}
    </div>
  );
}

/**
 * A team's results per month: wins, draws and losses stacked.
 *
 * Bars, not the three overlapping smoothed areas this used to be. The data is
 * a count of matches in each month — a handful of whole numbers — and a curve
 * drawn through them invents values between the points (2.4 wins in a month
 * with none played). A stacked bar shows exactly what was counted, and its
 * height is the number of matches played.
 *
 * (The component keeps its historical name; it charts results, not
 * probabilities.)
 */
export function WinProbabilityChart({ data, teamName }: WinProbabilityChartProps) {
  const totals = data.reduce(
    (acc, d) => ({ w: acc.w + d.wins, d: acc.d + d.draws, l: acc.l + d.losses }),
    { w: 0, d: 0, l: 0 }
  );
  const played = totals.w + totals.d + totals.l;
  const summary = `${teamName}: ${played} matches across ${data.length} months with at least one match — ${totals.w} won, ${totals.d} drawn, ${totals.l} lost.`;

  return (
    <figure className="rounded-lg border border-border bg-surface p-4 sm:p-5">
      <figcaption className="mb-4">
        <p className="font-display text-lg font-semibold uppercase tracking-wide text-foreground">Results by month</p>
        <p className="mt-1 text-xs leading-relaxed text-fg-subtle">
          Matches played each month, split into wins, draws and losses. Months with no match are not shown.
        </p>
      </figcaption>

      {/* The chart is a picture of the table below it; assistive technology
          gets the summary and the table instead. */}
      <div role="img" aria-label={summary}>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 4, right: 4, left: -24, bottom: 0 }} barCategoryGap="22%">
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis
              dataKey="date"
              tickFormatter={monthLabel}
              tick={{ fill: "var(--fg-subtle)", fontSize: 11 }}
              axisLine={{ stroke: "var(--border-strong)" }}
              tickLine={false}
              minTickGap={16}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: "var(--fg-subtle)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              label={{ value: "Matches", angle: -90, position: "insideLeft", offset: 34, fill: "var(--fg-subtle)", fontSize: 11 }}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--surface-2)" }} />
            <Legend iconType="square" iconSize={9} wrapperStyle={{ fontSize: 12, color: "var(--fg-muted)", paddingTop: 8 }} />
            <Bar dataKey="wins" name="Won" stackId="r" fill="var(--win)" isAnimationActive={false} />
            <Bar dataKey="draws" name="Drawn" stackId="r" fill="var(--draw)" isAnimationActive={false} />
            <Bar dataKey="losses" name="Lost" stackId="r" fill="var(--loss)" radius={[2, 2, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <details className="mt-3">
        <summary className="cursor-pointer rounded text-xs font-semibold text-fg-muted hover:text-foreground">
          Show the figures as a table
        </summary>
        <div className="mt-2 max-h-64 overflow-auto rounded-md border border-border">
          <table className="w-full text-xs">
            <caption className="sr-only">{summary}</caption>
            <thead className="sticky top-0 bg-surface-2">
              <tr>
                <th scope="col" className="eyebrow px-3 py-1.5 text-left">Month</th>
                <th scope="col" className="eyebrow px-2 py-1.5 text-right">Won</th>
                <th scope="col" className="eyebrow px-2 py-1.5 text-right">Drawn</th>
                <th scope="col" className="eyebrow px-2 py-1.5 text-right">Lost</th>
                <th scope="col" className="eyebrow px-2 py-1.5 text-right">Goals for</th>
                <th scope="col" className="eyebrow px-3 py-1.5 text-right">Goals against</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.map((d) => (
                <tr key={d.date}>
                  <th scope="row" className="px-3 py-1.5 text-left font-normal text-fg-muted">{monthLabel(d.date)}</th>
                  <td className="px-2 py-1.5 text-right text-foreground">{d.wins}</td>
                  <td className="px-2 py-1.5 text-right text-foreground">{d.draws}</td>
                  <td className="px-2 py-1.5 text-right text-foreground">{d.losses}</td>
                  <td className="px-2 py-1.5 text-right text-fg-muted">{d.goals_scored}</td>
                  <td className="px-3 py-1.5 text-right text-fg-muted">{d.goals_conceded}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
