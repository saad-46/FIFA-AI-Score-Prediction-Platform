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
  confederation: string;
  fifa_ranking?: number;
  logo_url?: string;
  founded_year?: number;
  home_stadium?: string;
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

export interface Match {
  id: string;
  date: string;
  home_team_id: string;
  away_team_id: string;
  home_team: Team;
  away_team: Team;
  home_score: number | null;
  away_score: number | null;
  tournament: string;
  stage?: string;
  neutral_venue: boolean;
  city?: string;
  country?: string;
  status: "scheduled" | "live" | "completed";
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

export interface PredictionResult {
  home_team: string;
  away_team: string;
  predicted_home_score: number;
  predicted_away_score: number;
  home_win_probability: number;
  draw_probability: number;
  away_win_probability: number;
  home_expected_goals: number;
  away_expected_goals: number;
  confidence_score: number;
  model_version: string;
  prediction_id: string;
  insights: PredictionInsight[];
  head_to_head: HeadToHeadStats;
  created_at: string;
}

export interface PredictionInsight {
  type: "advantage" | "warning" | "neutral";
  title: string;
  description: string;
  impact: "high" | "medium" | "low";
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
  confidence_score: number;
  actual_home_score?: number;
  actual_away_score?: number;
  was_correct?: boolean;
  created_at: string;
}

// ─── Head to Head ─────────────────────────────────────────────────────────────

export interface HeadToHeadStats {
  total_matches: number;
  home_team_wins: number;
  away_team_wins: number;
  draws: number;
  home_team_goals: number;
  away_team_goals: number;
  last_5_matches: Match[];
}

// ─── Analytics ───────────────────────────────────────────────────────────────

export interface TournamentStats {
  tournament: string;
  total_matches: number;
  total_goals: number;
  avg_goals_per_match: number;
  highest_scoring_match: Match;
  top_scoring_team: Team;
  most_clean_sheets: Team;
  year?: number;
}

export interface GoalDistribution {
  minute: number;
  goals: number;
}

export interface ScorelineFrequency {
  scoreline: string;
  count: number;
  percentage: number;
}

export interface PerformanceTrend {
  date: string;
  wins: number;
  draws: number;
  losses: number;
  goals_scored: number;
  goals_conceded: number;
}

// ─── API Responses ────────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: "success" | "error";
}

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
  recent_predictions: SavedPrediction[];
  top_teams: TeamStats[];
  upcoming_matches: Match[];
}
