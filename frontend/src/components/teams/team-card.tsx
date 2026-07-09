import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { cn, getResultBg } from "@/lib/utils";
import type { TeamStats } from "@/types";

interface TeamCardProps {
  stats: TeamStats;
  rank?: number;
  delay?: number;
}

/** Server Component — leaderboard-style team card with form (W/D/L) strip. */
export function TeamCard({ stats, rank, delay = 0 }: TeamCardProps) {
  const winRate = (stats.win_rate * 100).toFixed(1);
  const goalDiff = stats.goal_difference;

  return (
    <Link
      href={`/teams/${stats.team_id}`}
      className="block animate-in fade-in slide-in-from-bottom-2 fill-mode-both"
      style={{ animationDelay: `${delay}s`, animationDuration: "0.35s" }}
    >
      <Card interactive className="group hover:border-primary/30 hover:shadow-primary/5">
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            {rank && <span className="w-6 text-center text-lg font-black text-fg-muted/60">{rank}</span>}
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-2 text-lg font-bold text-foreground">
              {stats.team_name[0]}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold text-foreground group-hover:text-primary transition-colors">
                {stats.team_name}
              </p>
              <p className="text-xs text-fg-muted">{stats.matches_played} matches</p>
            </div>
            <div className="text-right">
              <p className="text-sm font-bold font-mono text-foreground">{winRate}%</p>
              <p className="text-xs text-fg-muted">win rate</p>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-4 gap-2 text-center text-xs">
            <div className="rounded bg-win/10 py-1">
              <p className="font-bold font-mono text-win">{stats.wins}</p>
              <p className="text-fg-muted">W</p>
            </div>
            <div className="rounded bg-draw/10 py-1">
              <p className="font-bold font-mono text-draw">{stats.draws}</p>
              <p className="text-fg-muted">D</p>
            </div>
            <div className="rounded bg-loss/10 py-1">
              <p className="font-bold font-mono text-loss">{stats.losses}</p>
              <p className="text-fg-muted">L</p>
            </div>
            <div
              className={cn(
                "rounded py-1",
                goalDiff > 0 ? "bg-win/10" : goalDiff < 0 ? "bg-loss/10" : "bg-surface-2"
              )}
            >
              <p
                className={cn(
                  "font-bold font-mono",
                  goalDiff > 0 ? "text-win" : goalDiff < 0 ? "text-loss" : "text-fg-muted"
                )}
              >
                {goalDiff > 0 ? "+" : ""}
                {goalDiff}
              </p>
              <p className="text-fg-muted">GD</p>
            </div>
          </div>

          {stats.form && stats.form.length > 0 && (
            <div className="mt-3 flex items-center gap-1">
              <span className="mr-1 text-xs text-fg-muted">Form:</span>
              {stats.form.slice(-5).map((result, i) => (
                <span
                  key={i}
                  className={cn(
                    "inline-flex h-5 w-5 items-center justify-center rounded border text-xs font-bold",
                    getResultBg(result)
                  )}
                >
                  {result}
                </span>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
