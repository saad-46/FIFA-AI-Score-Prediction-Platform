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
