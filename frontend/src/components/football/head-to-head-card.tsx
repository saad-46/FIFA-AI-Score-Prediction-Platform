import { Shield } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { EmptyState } from "@/components/ui/empty-state";
import type { HeadToHeadStats } from "@/types";

interface HeadToHeadCardProps {
  stats: HeadToHeadStats;
  homeTeam: string;
  awayTeam: string;
}

export function HeadToHeadCard({ stats, homeTeam, awayTeam }: HeadToHeadCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-accent" aria-hidden="true" />
          Head to Head
        </CardTitle>
      </CardHeader>
      <CardContent>
        {stats.total_matches === 0 ? (
          <EmptyState
            icon={Shield}
            title="No previous meetings"
            description={`${homeTeam} and ${awayTeam} haven't met in this dataset.`}
            className="py-6"
          />
        ) : (
          <>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold text-win">{stats.home_team_wins}</p>
                <p className="text-xs text-fg-muted mt-1">{homeTeam} wins</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-draw">{stats.draws}</p>
                <p className="text-xs text-fg-muted mt-1">Draws</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-loss">{stats.away_team_wins}</p>
                <p className="text-xs text-fg-muted mt-1">{awayTeam} wins</p>
              </div>
            </div>
            <Separator className="my-4" />
            <div className="grid grid-cols-2 gap-4 text-center text-sm">
              <div>
                <p className="text-fg-muted">Total matches</p>
                <p className="font-semibold text-foreground">{stats.total_matches}</p>
              </div>
              <div>
                <p className="text-fg-muted">Goals</p>
                <p className="font-semibold text-foreground">
                  {stats.home_team_goals} – {stats.away_team_goals}
                </p>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
