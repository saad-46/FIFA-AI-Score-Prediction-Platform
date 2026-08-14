import { Calendar, MapPin } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, formatDate } from "@/lib/utils";
import type { Match } from "@/types";
import { getCountryFlag } from "@/components/football/team-identity";

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
    // Presentational, not a link. It previously wrapped a Link to
    // /matches/{id} — a route that does not exist, so every click 404'd.
    // Hover feedback is kept (border, lift, background) because the card is
    // part of a scannable list, but `cursor-default` and the absence of
    // `interactive` stop it advertising a click it cannot honour.
    <div
      className="block animate-in fade-in slide-in-from-bottom-2 fill-mode-both cursor-default"
      style={{ animationDelay: `${delay}s`, animationDuration: "0.3s" }}
    >
      <Card className="group border-border/40 bg-surface/30 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:bg-surface-2/30">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 text-xs text-fg-muted font-mono">
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
              <Badge variant="outline" className="text-[10px] font-mono uppercase tracking-wider border-border/60">
                {match.tournament}
              </Badge>
            </div>
          </div>

          <div className="flex items-center justify-between">
            {/* Home Team */}
            <div className="flex-1 flex items-center justify-end gap-2.5 min-w-0">
              <p className="truncate font-semibold text-foreground group-hover:text-primary transition-colors text-sm md:text-base">
                {match.home_team.name}
              </p>
              <span className="text-xl select-none shrink-0" aria-hidden="true">
                {getCountryFlag(match.home_team.name, match.home_team.fifa_code)}
              </span>
            </div>

            {/* Score Center */}
            <div className="mx-4 text-center min-w-[90px] shrink-0">
              {isCompleted ? (
                <div className="flex items-center justify-center gap-2">
                  <span className="font-mono text-xl font-bold text-foreground">{match.home_score}</span>
                  <span className="text-fg-muted/40 font-bold">—</span>
                  <span className="font-mono text-xl font-bold text-foreground">{match.away_score}</span>
                </div>
              ) : isLive ? (
                <div className="flex items-center justify-center gap-2">
                  <span className="font-mono text-xl font-bold text-loss">{match.home_score ?? 0}</span>
                  <span className="text-loss animate-pulse">•</span>
                  <span className="font-mono text-xl font-bold text-loss">{match.away_score ?? 0}</span>
                </div>
              ) : (
                <span className="text-xs font-mono font-bold tracking-widest text-zinc-500 uppercase">VS</span>
              )}
              {match.stage && <p className="text-[9px] font-mono text-fg-muted/70 uppercase tracking-wider mt-1">{match.stage}</p>}
            </div>

            {/* Away Team */}
            <div className="flex-1 flex items-center justify-start gap-2.5 min-w-0">
              <span className="text-xl select-none shrink-0" aria-hidden="true">
                {match.away_team ? getCountryFlag(match.away_team.name, match.away_team.fifa_code) : "⚽"}
              </span>
              {/* An unresolved opponent is a property of a *scheduled* fixture.
                  Rendering the literal "TBD" on a completed match would read as
                  a team name, so that case says the opponent is missing. */}
              <p
                className={cn(
                  "truncate font-semibold transition-colors text-sm md:text-base",
                  match.away_team
                    ? "text-foreground group-hover:text-primary"
                    : "italic text-fg-muted"
                )}
              >
                {match.away_team?.name ?? (isCompleted ? "Opponent not recorded" : "To be decided")}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
