import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ScorelineFrequency } from "@/types";

interface ScorelineFrequencyChartProps {
  data: ScorelineFrequency[];
}

export function ScorelineFrequencyChart({ data }: ScorelineFrequencyChartProps) {
  if (data.length === 0) return null;
  const max = Math.max(...data.map((d) => d.percentage));

  return (
    <Card>
      <CardHeader className="border-b border-border pb-3">
        <CardTitle className="font-display text-lg font-semibold uppercase tracking-wide text-foreground">
          Most common scorelines
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-4">
        <ol className="space-y-2" aria-label="Scorelines by how often they occurred">
          {data.map((s) => (
            <li key={s.scoreline} className="grid grid-cols-[2.5rem_1fr_7rem] items-center gap-3">
              <span className="tabular text-sm font-semibold text-foreground">{s.scoreline}</span>
              <span className="h-2 overflow-hidden rounded-full bg-surface-3" aria-hidden="true">
                <span className="block h-full rounded-full bg-primary" style={{ width: `${(s.percentage / max) * 100}%` }} />
              </span>
              <span className="tabular text-right text-sm text-fg-muted">
                <span className="font-semibold text-foreground">{s.percentage.toFixed(1)}%</span>
                <span className="ml-1.5 text-xs text-fg-subtle">{s.count.toLocaleString()}</span>
              </span>
            </li>
          ))}
        </ol>
        <p className="pt-3 text-xs leading-relaxed text-fg-subtle">
          Share of matches in the dataset that ended with each score, first-listed team&apos;s goals first; the
          count is beside it. Bars are scaled to the most common score.
        </p>
      </CardContent>
    </Card>
  );
}
