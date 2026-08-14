import type { BracketNodeData, MatchSource, WcStage } from "@/types";
import { WC_STAGE_LABELS } from "@/types";

/**
 * Presentation helpers for WC2026 bracket data.
 *
 * Kept out of components so the same score/label logic is used by the bracket
 * node, the detail dialog and the backtest table — a knockout tie must read
 * identically wherever it appears.
 */

export function stageLabel(stage: WcStage): string {
  return WC_STAGE_LABELS[stage] ?? stage;
}

/** Short label for tight spaces (bracket column headers, mobile tabs). */
export function stageShortLabel(stage: WcStage): string {
  switch (stage) {
    case "group_stage":
      return "Groups";
    case "round_of_32":
      return "R32";
    case "round_of_16":
      return "R16";
    case "quarter_final":
      return "QF";
    case "semi_final":
      return "SF";
    case "third_place":
      return "3rd";
    case "final":
      return "Final";
    default:
      return stage;
  }
}

/**
 * The score to show for a completed match, with the decisive phase made
 * explicit.
 *
 * A tie that went to extra time or penalties must never render as a bare draw
 * beside a winner — that reads as broken data. Mirrors `_display_score` in
 * `app/data/wc2026`, which formats the same thing server-side for the backtest.
 */
export function formatScore(node: BracketNodeData): string | null {
  if (node.home_score === null || node.away_score === null) return null;

  if (node.home_penalties !== null && node.away_penalties !== null) {
    return `${node.home_score}-${node.away_score}`;
  }
  if (node.home_score_et !== null && node.away_score_et !== null) {
    return `${node.home_score_et}-${node.away_score_et}`;
  }
  return `${node.home_score}-${node.away_score}`;
}

/** The "(aet)" / "(4-3 pens)" qualifier, or null for a normal-time result. */
export function scoreQualifier(node: BracketNodeData): string | null {
  if (node.home_penalties !== null && node.away_penalties !== null) {
    return `${node.home_penalties}-${node.away_penalties} pens`;
  }
  if (node.home_score_et !== null && node.away_score_et !== null) {
    return "aet";
  }
  return null;
}

/** Per-side score for a two-row bracket node, using the decisive phase. */
export function sideScores(node: BracketNodeData): { home: number | null; away: number | null } {
  if (node.home_score_et !== null && node.away_score_et !== null) {
    return { home: node.home_score_et, away: node.away_score_et };
  }
  return { home: node.home_score, away: node.away_score };
}

/** Human-readable description of an unresolved slot, e.g. "Winner of match 89". */
export function sourceLabel(source: MatchSource | null): string {
  if (!source) return "TBD";
  switch (source.type) {
    case "winner_of":
      return source.match_number ? `Winner of match ${source.match_number}` : "Winner TBD";
    case "loser_of":
      return source.match_number ? `Loser of match ${source.match_number}` : "Loser TBD";
    case "group_qualification":
      return "Group qualifier";
    case "group_fixture":
      return "Group fixture";
    default:
      return "TBD";
  }
}

/** Did the frozen model call this match correctly? `null` when either the
 * prediction or the result is missing — never guess. */
export function predictionOutcome(node: BracketNodeData): boolean | null {
  const predicted = node.prediction?.predicted_winner;
  if (!predicted || node.status !== "completed") return null;

  const actual =
    node.winner_team ??
    (node.home_score !== null && node.away_score !== null && node.home_score === node.away_score
      ? "Draw"
      : null);
  if (!actual) return null;
  return predicted === actual;
}

/** Formats a 0–1 probability as a whole percentage. */
export function asPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
}

/** Date as "24 Jun", locale-independent so server and client agree. */
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatMatchDate(iso: string | null): string | null {
  if (!iso) return null;
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return null;
  return `${day} ${MONTHS[month - 1]}`;
}
