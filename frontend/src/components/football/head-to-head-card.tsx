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
      <CardHeader className="border-b border-border pb-3">
        <CardTitle className="flex items-center gap-2 font-display text-lg font-semibold uppercase tracking-wide text-foreground">
          Head to head
        </CardTitle>
      </CardHeader>
      <CardContent>
        {stats.total_matches === 0 ? (
          // Never "No previous meetings": the corpus is World Cup only, so two
          // sides can have met many times in friendlies or qualifiers and still
          // show zero here. The scope has to be stated for the zero to be true.
          <EmptyState
            icon={Shield}
            title="No World Cup meetings"
            description={
              stats.scope_label
                ? `${homeTeam} and ${awayTeam} have not met within ${stats.scope_label.toLowerCase()}. Matches outside this dataset are not counted.`
                : `${homeTeam} and ${awayTeam} have not met in the dataset used here.`
            }
            className="py-6"
          />
        ) : (
          <>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="scoreline text-3xl text-foreground">{stats.home_team_wins}</p>
                <p className="text-xs text-fg-muted mt-1">{homeTeam} wins</p>
              </div>
              <div>
                <p className="scoreline text-3xl text-fg-muted">{stats.draws}</p>
                <p className="text-xs text-fg-muted mt-1">Draws</p>
              </div>
              <div>
                <p className="scoreline text-3xl text-foreground">{stats.away_team_wins}</p>
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
            {stats.scope_label && (
              <p className="pt-3 text-center text-xs text-fg-subtle">{stats.scope_label}</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
