// ─── Auth ────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name?: string;
  avatar_url?: string;
  role: "user" | "admin";
  created_at: string;
}

// ─── Teams ───────────────────────────────────────────────────────────────────

export interface Team {
  id: string;
  name: string;
  country: string;
  confederation?: string;
  fifa_ranking?: number;
  elo_rating?: number;
  fifa_code?: string;
  wc2026_group?: string;
  ranking_updated_at?: string;
  logo_url?: string;
  founded_year?: number;
  home_stadium?: string;
  created_at?: string;
}

export interface TeamStats {
  team_id: string;
  team_name: string;
  matches_played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_scored: number;
  goals_conceded: number;
  goal_difference: number;
  win_rate: number;
  avg_goals_scored: number;
  avg_goals_conceded: number;
  clean_sheets: number;
  form: Array<"W" | "D" | "L">;
}

// ─── Matches ─────────────────────────────────────────────────────────────────

// away_team/away_team_id are genuinely nullable: some WC2026 knockout fixtures
// have an unresolved opponent (e.g. a Round-of-16 TBD slot).
export interface Match {
  id: string;
  date: string;
  home_team_id: string;
  away_team_id: string | null;
  home_team: Team;
  away_team: Team | null;
  home_score: number | null;
  away_score: number | null;
  tournament: string;
  stage?: string;
  stage_id?: number;
  tournament_year?: number;
  neutral_venue: boolean;
  city?: string;
  country?: string;
  home_xg?: number;
  away_xg?: number;
  external_match_id?: string;
  data_source?: string;
  status: "scheduled" | "live" | "completed";
}

export interface TeamStatistics {
  match_id: string;
  team_id: string;
  possession?: number;
  shots?: number;
  shots_on_target?: number;
  corners?: number;
  fouls?: number;
  offsides?: number;
  saves?: number;
  player_of_the_match?: string;
}

export interface MatchDetail extends Match {
  team_statistics: TeamStatistics[];
}

export interface MatchResult {
  result: "W" | "D" | "L";
  team_id: string;
}

// ─── Predictions ─────────────────────────────────────────────────────────────

export interface PredictionRequest {
  home_team: string;
  away_team: string;
  tournament?: string;
  neutral_venue?: boolean;
}

export interface ScorelineProbability {
  score: string;
  probability: number;
}

export interface FeatureAttribution {
  feature: string;
  readable_name: string;
  impact: number;
}

export interface PredictionExplanation {
  predicted_outcome: string;
  confidence: number;
  top_positive_features: FeatureAttribution[];
  top_negative_features: FeatureAttribution[];
}

export interface PredictionInsight {
  type: "advantage" | "warning" | "neutral";
  title: string;
  description: string;
  impact: "high" | "medium" | "low";
}

export interface PredictionResult {
  prediction_id: string;
  home_team: string;
  away_team: string;
  predicted_home_score: number;
  predicted_away_score: number;
  // Field names match the live API exactly (expected_<side>_goals, not
  // <side>_expected_goals) — this was inverted in a previous version of this
  // file and silently broke every consumer.
  expected_home_goals: number;
  expected_away_goals: number;
  home_win_probability: number;
  draw_probability: number;
  away_win_probability: number;
  most_likely_score: string;
  top_scorelines: ScorelineProbability[];
  prediction_explanation: PredictionExplanation;
  confidence_score: number;
  model_version: string;
  insights: PredictionInsight[];
  head_to_head: HeadToHeadStats;
  created_at: string;
}

export interface SavedPrediction {
  id: string;
  user_id: string;
  prediction_id: string;
  home_team: string;
  away_team: string;
  predicted_home_score: number;
  predicted_away_score: number;
  home_win_probability: number;
  draw_probability: number;
  away_win_probability: number;
  expected_home_goals: number;
  expected_away_goals: number;
  confidence_score: number;
  model_version: string;
  actual_home_score?: number | null;
  actual_away_score?: number | null;
  was_correct?: boolean | null;
  created_at: string;
}

export interface AccuracyStats {
  total: number;
  correct: number;
  accuracy: number;
}

// ─── Head to Head ─────────────────────────────────────────────────────────────

export interface HeadToHeadStats {
  total_matches: number;
  home_team_wins: number;
  away_team_wins: number;
  draws: number;
  home_team_goals: number;
  away_team_goals: number;
  last_5_matches?: Match[];
  /** Which corpus the counts were drawn from. Render it: zero meetings in a
   * World-Cup-only dataset does not mean two teams have never played. */
  scope?: string | null;
  scope_label?: string | null;
}

// ─── Analytics ───────────────────────────────────────────────────────────────

export interface TournamentStats {
  total_matches: number;
  total_goals: number;
  avg_goals_per_match: number;
  home_win_rate: number;
  draw_rate: number;
  away_win_rate: number;
  top_scoring_team: string;
  most_goals_in_match: number;
}

export interface GoalDistribution {
  minute: number;
  goals: number;
  // Every point is currently synthetic placeholder data (no goal-minute-level
  // data exists in the DB yet) — always surface this in the UI, never hide it.
  is_synthetic: boolean;
}

export interface ScorelineFrequency {
  scoreline: string;
  count: number;
  percentage: number;
}

export interface PerformanceTrendPoint {
  date: string;
  wins: number;
  draws: number;
  losses: number;
  goals_scored: number;
  goals_conceded: number;
}

export interface GlobalAnalytics {
  total_matches: number;
  total_goals: number;
  avg_goals_per_match: number;
  home_win_rate: number;
  draw_rate: number;
  away_win_rate: number;
  goals_by_year: Array<{ year: number; goals: number; matches: number }>;
  top_tournaments: Array<{ tournament: string; matches: number }>;
}

export interface ModelMetrics {
  accuracy: number;
  mae: number;
  rmse: number;
  last_trained: string;
  training_samples: number;
  model_version: string;
}

export interface FeatureImportance {
  feature: string;
  importance: number;
}

export interface FeatureImportanceResponse {
  features: FeatureImportance[];
  model_version: string;
  total_features: number;
}

// ─── Tournament (FIFA World Cup 2026) ──────────────────────────────────────────

export interface Fifa2026Team {
  code: string;
  name: string;
}

export interface Fifa2026Group {
  name: string;
  teams: Fifa2026Team[];
}

export interface Fifa2026GroupsResponse {
  groups: Fifa2026Group[];
}

export interface Fifa2026Match {
  match_number: number;
  date: string;
  kickoff_time_et: string;
  venue_city: string;
  stage: string;
  group?: string;
  // 3-letter FIFA code, or a placeholder like "W53"/"L101" for a still-undetermined
  // knockout slot.
  home_team: string;
  away_team: string;
  uncertain?: boolean;
}

export interface Fifa2026ScheduleResponse {
  matches: Fifa2026Match[];
}

// ─── WC2026 bracket / standings / backtest (V2 canonical data) ────────────────
// Backed by GET /tournament/2026/{bracket,standings,teams,backtest}. Distinct
// from the Fifa2026* wallchart types above: those describe what was *scheduled*
// (with W53/L101 placeholders); these describe the real bracket, its
// progression wiring, and what actually happened.

/** Stage identifiers, in playing order. */
export type WcStage =
  | "group_stage"
  | "round_of_32"
  | "round_of_16"
  | "quarter_final"
  | "semi_final"
  | "third_place"
  | "final";

export const WC_STAGE_ORDER: WcStage[] = [
  "group_stage",
  "round_of_32",
  "round_of_16",
  "quarter_final",
  "semi_final",
  "third_place",
  "final",
];

export const WC_STAGE_LABELS: Record<WcStage, string> = {
  group_stage: "Group Stage",
  round_of_32: "Round of 32",
  round_of_16: "Round of 16",
  quarter_final: "Quarter-Finals",
  semi_final: "Semi-Finals",
  third_place: "Third Place",
  final: "Final",
};

/** Where a fixture's participant comes from. Drives bracket connectors — the
 * frontend must never hardcode these relationships. */
export interface MatchSource {
  type: "group_fixture" | "group_qualification" | "winner_of" | "loser_of";
  match_number?: number | null;
}

export interface BracketMatchPrediction {
  predicted_winner: string | null;
  home_win_probability: number | null;
  draw_probability: number | null;
  away_win_probability: number | null;
  predicted_home_goals: number | null;
  predicted_away_goals: number | null;
  most_likely_score: string | null;
  model_version: string | null;
}

export interface BracketNodeData {
  match_number: number;
  stage: WcStage;
  is_knockout: boolean;
  group: string | null;
  date: string | null;
  kickoff_time_et: string | null;
  venue: string | null;
  city: string | null;
  home_team: string | null;
  away_team: string | null;
  /** Full-time score. For ties decided later, see *_score_et / *_penalties. */
  home_score: number | null;
  away_score: number | null;
  /** Score after extra time — the running total, not ET-only goals. */
  home_score_et: number | null;
  away_score_et: number | null;
  home_penalties: number | null;
  away_penalties: number | null;
  result_method: string | null;
  winner_team: string | null;
  status: "completed" | "scheduled";
  home_source: MatchSource | null;
  away_source: MatchSource | null;
  feeds_winner_to: number | null;
  feeds_loser_to: number | null;
  prediction: BracketMatchPrediction | null;
}

export interface StageRange {
  stage: WcStage;
  first: number;
  last: number;
}

export interface BracketResponse {
  format: string | null;
  stage_ranges: StageRange[];
  nodes: BracketNodeData[];
}

export interface StandingRow {
  team: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
  position: number;
}

export interface GroupStanding {
  group: string;
  standings: StandingRow[];
}

export interface StandingsResponse {
  groups: GroupStanding[];
}

export interface Wc2026TeamMeta {
  team_name: string;
  fifa_code: string | null;
  confederation: string | null;
  group: string | null;
  fifa_ranking: number | null;
  elo_rating: number | null;
}

export interface Wc2026TeamsResponse {
  teams: Record<string, Wc2026TeamMeta>;
}

export interface BacktestStageAccuracy {
  stage: WcStage;
  correct: number;
  total: number;
  accuracy: number;
}

export interface BacktestMatch {
  match_number: number | null;
  match: string | null;
  stage: WcStage;
  predicted: string | null;
  actual: string | null;
  correct: boolean;
  home_win_probability: number | null;
  draw_probability: number | null;
  away_win_probability: number | null;
  predicted_score: string | null;
  actual_score: string | null;
}

/** The shipped model's headline evaluation.
 *
 * `evaluation_name` exists so a UI can never render a bare "Model Accuracy"
 * percentage — the number is only meaningful with the evaluation it came from.
 * `legacy` carries the superseded v1 training metrics for provenance. */
export interface ModelEvaluation {
  model_version: string;
  evaluation_name: string;
  evaluation_description: string;
  accuracy: number | null;
  correct: number | null;
  total: number | null;
  is_out_of_sample: boolean;
  by_stage: BacktestStageAccuracy[];
  legacy: {
    model_version?: string;
    label?: string;
    classifier_raw_accuracy?: number | null;
    classifier_adjusted_accuracy?: number | null;
    home_mae?: number | null;
    training_samples?: number | null;
    trained_at?: string | null;
    note?: string;
  } | null;
}

/** Historical evaluation of a model frozen before any 2026 result was seen.
 * Never render this as a forecast. */
export interface BacktestResponse {
  model_version: string | null;
  n_matches_scored: number | null;
  accuracy: number | null;
  correct: number;
  by_stage: BacktestStageAccuracy[];
  actual_champion: string | null;
  predicted_champion: string | null;
  note: string | null;
  matches: BacktestMatch[];
}

export interface TournamentSimulationRequest {
  use_fifa_2026_groups?: boolean;
  groups?: Record<string, string[]>;
  n_simulations: number;
  use_real_results?: boolean;
}

export interface TeamTournamentProbabilities {
  group: number;
  r32: number;
  r16: number;
  qf: number;
  sf: number;
  third_place: number;
  final: number;
  winner: number;
}

export interface TournamentSimulationResponse {
  // Keyed by 3-letter FIFA team code.
  probabilities: Record<string, TeamTournamentProbabilities>;
}

// ─── API Responses ────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export interface DashboardStats {
  total_predictions: number;
  accuracy_rate: number;
  total_matches_analyzed: number;
  total_teams: number;
  recent_predictions?: SavedPrediction[];
  top_teams?: TeamStats[];
  upcoming_matches?: Match[];
}

// ─── WC2026 squads ───────────────────────────────────────────────────────────

/**
 * A player from the committed squad dataset.
 *
 * Every statistic is optional because the source only fills one in when it
 * genuinely exists: 198 of the 1,248 squad members have no appearances at all,
 * and 78 of the 136 goalkeepers never kept goal. `null`/absent means "not
 * available" and must render as such — never as 0.
 */
export interface Player {
  name: string;
  team: string;
  position: string | null;
  age: number | null;
  birth_year: number | null;
  club: string | null;
  is_goalkeeper: boolean;

  games: number | null;
  games_starts: number | null;
  minutes: number | null;

  goals: number | null;
  assists: number | null;
  shots: number | null;
  shots_on_target: number | null;
  goals_per90: number | null;
  assists_per90: number | null;

  crosses: number | null;
  fouled: number | null;
  offsides: number | null;
  cards_yellow: number | null;
  cards_red: number | null;

  tackles_won: number | null;
  interceptions: number | null;
  fouls: number | null;

  gk_games: number | null;
  gk_minutes: number | null;
  gk_goals_against: number | null;
  gk_saves: number | null;
  gk_save_pct: number | null;
  gk_clean_sheets: number | null;
  gk_clean_sheets_pct: number | null;
}

export interface TeamSquad {
  team: string;
  fifa_code: string | null;
  wc2026_group: string | null;
  squad_size: number;
  players_with_appearances: number;
  /** Captain of the team's most recent 2026 match. Null when unavailable. */
  captain: Player | null;
  players: Player[];
  total_goals: number;
  total_assists: number;
  total_minutes: number;
}
