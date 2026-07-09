import Link from "next/link";
import { Calendar, MapPin } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import type { Match } from "@/types";

interface MatchCardProps {
  match: Match;
  delay?: number;
}

/** Server Component — also covers "fixture" display (an unplayed, scheduled
 * match just renders "vs" instead of a score), so no separate FixtureCard
 * is needed. */
export function MatchCard({ match, delay = 0 }: MatchCardProps) {
  const isCompleted = match.status === "completed";
  const isLive = match.status === "live";

  return (
    <Link
      href={`/matches/${match.id}`}
      className="block animate-in fade-in slide-in-from-bottom-2 fill-mode-both"
      style={{ animationDelay: `${delay}s`, animationDuration: "0.3s" }}
    >
      <Card interactive className="group">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 text-xs text-fg-muted">
              <Calendar className="h-3.5 w-3.5" aria-hidden="true" />
              {formatDate(match.date)}
              {match.city && (
                <>
                  <MapPin className="h-3.5 w-3.5 ml-1" aria-hidden="true" />
                  {match.city}
                </>
              )}
            </div>
            <div className="flex items-center gap-2">
              {isLive && <Badge variant="live">LIVE</Badge>}
              <Badge variant="secondary" className="text-xs">
                {match.tournament}
              </Badge>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex-1 text-right">
              <p className="font-semibold text-foreground group-hover:text-primary transition-colors">
                {match.home_team.name}
              </p>
              <p className="text-xs text-fg-muted">{match.home_team.country}</p>
            </div>

            <div className="mx-4 text-center min-w-[80px]">
              {isCompleted ? (
                <div className="flex items-center justify-center gap-2">
                  <span className="font-mono text-2xl font-black text-foreground">{match.home_score}</span>
                  <span className="text-fg-muted">—</span>
                  <span className="font-mono text-2xl font-black text-foreground">{match.away_score}</span>
                </div>
              ) : isLive ? (
                <div className="flex items-center justify-center gap-2">
                  <span className="font-mono text-2xl font-black text-loss">{match.home_score ?? 0}</span>
                  <span className="text-loss animate-pulse">•</span>
                  <span className="font-mono text-2xl font-black text-loss">{match.away_score ?? 0}</span>
                </div>
              ) : (
                <span className="text-sm font-medium text-fg-muted">vs</span>
              )}
              {match.stage && <p className="text-xs text-fg-muted/70 mt-0.5">{match.stage}</p>}
            </div>

            <div className="flex-1 text-left">
              <p className="font-semibold text-foreground group-hover:text-primary transition-colors">
                {match.away_team?.name ?? "TBD"}
              </p>
              <p className="text-xs text-fg-muted">
                {match.away_team?.country ?? "Opponent not yet determined"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
