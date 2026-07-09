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
      <CardHeader>
        <CardTitle>Most Common Scorelines</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {data.map((s) => (
          <div key={s.scoreline} className="flex items-center gap-3">
            <span className="w-10 shrink-0 font-mono text-sm font-semibold text-foreground">{s.scoreline}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-primary transition-all duration-700 ease-out"
                style={{ width: `${(s.percentage / max) * 100}%` }}
              />
            </div>
            <span className="w-20 shrink-0 text-right text-xs text-fg-muted">
              {s.percentage.toFixed(1)}% ({s.count.toLocaleString()})
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
