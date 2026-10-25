import { cn } from "@/lib/utils";
import type { Match } from "@/types";
import { TeamFlag } from "@/components/football/team-flag";

interface MatchCardProps {
  match: Match;
  /** Kept for call-site compatibility; rows no longer animate in one by one. */
  delay?: number;
}

/**
 * One match as a result line: home, score, away, then the competition.
 *
 * A row in a list rather than a card in a grid. Results are scanned down a
 * column of scores, and the two-column card grid put the score of every second
 * match on the far side of the page.
 *
 * Three states, each said in words: a completed match shows its score, a live
 * one is labelled "Live". A row with no score says "No result recorded" (past) or
 * "Scheduled" (future) -- a bare "vs"
 * left it to the reader to infer the match had no result.
 *
 * Server Component.
 */
/** The record stores stages as identifiers ("round_of_32"); show them as words. */
function readableStage(stage?: string | null): string | null {
  if (!stage) return null;
  const words = stage.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** How a knockout tie was settled, in words: "After extra time" or "Penalties 3–4"; null for a normal result. */
export function settledNote(match: Pick<Match, "result_method" | "home_penalties" | "away_penalties">): string | null {
  if (match.result_method === "Penalties" && match.home_penalties != null && match.away_penalties != null) {
    return `Penalties ${match.home_penalties}–${match.away_penalties}`;
  }
  if (match.result_method === "Extra Time") return "After extra time";
  return null;
}

export function MatchCard({ match }: MatchCardProps) {
  const isCompleted = match.status === "completed";
  const isLive = match.status === "live";
  const hasScore = match.home_score !== null && match.away_score !== null;
  // A shoot-out leaves the score level; the penalties say who went through.
  const shootout = match.home_penalties != null && match.away_penalties != null && match.home_penalties !== match.away_penalties;
  const homeWon = isCompleted && hasScore && (match.home_score! > match.away_score! || (match.home_score === match.away_score && shootout && match.home_penalties! > match.away_penalties!));
  const awayWon = isCompleted && hasScore && (match.away_score! > match.home_score! || (match.home_score === match.away_score && shootout && match.away_penalties! > match.home_penalties!));
  // A scheduled row dated in the past is not evidence the match was not played:
  // the record simply holds no result for it (the 2026 knockout rows are in this
  // state). Say what is known -- there is no recorded score -- and keep
  // "Scheduled" for a date that has not arrived.
  const today = new Date().toISOString().slice(0, 10);
  const noResultLabel = String(match.date).slice(0, 10) < today ? "No result recorded" : "Scheduled";
  const awayName = match.away_team?.name ?? (isCompleted ? "Opponent not recorded" : "To be decided");

  return (
    <li className="grid grid-cols-[1fr_auto_1fr] items-center gap-x-2 gap-y-1 bg-surface px-3 py-2.5 sm:grid-cols-[1fr_auto_1fr_minmax(0,11rem)] sm:gap-x-3 sm:px-4">
      <span className={cn("flex min-w-0 items-center justify-end gap-2 text-sm", homeWon ? "font-semibold text-foreground" : "text-fg-muted")}>
        <span className="text-right leading-tight">{match.home_team.name}</span>
        <TeamFlag name={match.home_team.name} fifaCode={match.home_team.fifa_code} size="sm" />
      </span>

      <span className="min-w-[4.25rem] text-center">
        {(isCompleted || isLive) && hasScore ? (
          <span className="scoreline text-xl text-foreground">
            {match.home_score}
            <span className="mx-1 text-fg-subtle" aria-hidden="true">
              –
            </span>
            <span className="sr-only"> to </span>
            {match.away_score}
          </span>
        ) : (
          <span className="text-xs leading-tight text-fg-subtle">{noResultLabel}</span>
        )}
        {settledNote(match) && (
          <span className="mt-0.5 block text-[10px] font-medium uppercase tracking-wide text-fg-subtle">{settledNote(match)}</span>
        )}
        {isLive && (
          <span className="mt-0.5 block text-[10px] font-bold uppercase tracking-wider text-loss">Live</span>
        )}
      </span>

      <span className={cn("flex min-w-0 items-center gap-2 text-sm", awayWon ? "font-semibold text-foreground" : "text-fg-muted")}>
        {match.away_team ? (
          <TeamFlag name={match.away_team.name} fifaCode={match.away_team.fifa_code} size="sm" />
        ) : (
          <TeamFlag name="Undecided" size="sm" />
        )}
        {/* An unresolved opponent is a property of a scheduled fixture. On a
            completed match the literal "TBD" would read as a team name, so that
            case says the opponent is missing. */}
        <span className={cn("leading-tight", !match.away_team && "italic")}>{awayName}</span>
      </span>

      <span className="col-span-3 text-center text-xs leading-snug text-fg-subtle sm:col-span-1 sm:text-right">
        {[match.tournament, readableStage(match.stage), match.city].filter(Boolean).join(" · ")}
      </span>
    </li>
  );
}
