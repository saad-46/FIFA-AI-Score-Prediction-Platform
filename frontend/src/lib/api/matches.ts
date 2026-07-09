import { apiClient } from "./client";
import type {
  Match,
  MatchDetail,
  TournamentStats,
  GoalDistribution,
  ScorelineFrequency,
  PaginatedResponse,
} from "@/types";

export const matchesApi = {
  /**
   * Get paginated match history. NOTE: `total` reflects the full historical
   * dataset (~49k rows across all competitions), not just the WC-only corpus
   * the ML pipeline uses — surface this honestly, don't be surprised by it.
   */
  async getHistory(
    page = 1,
    pageSize = 20,
    filters?: {
      team?: string;
      tournament?: string;
      year?: number;
      from_date?: string;
      to_date?: string;
    }
  ): Promise<PaginatedResponse<Match>> {
    const { data } = await apiClient.get<PaginatedResponse<Match>>(
      "/matches",
      { params: { page, page_size: pageSize, ...filters } }
    );
    return data;
  },

  /**
   * Get a single match by ID, including box-score team statistics when available.
   */
  async getById(id: string): Promise<MatchDetail> {
    const { data } = await apiClient.get<MatchDetail>(`/matches/${id}`);
    return data;
  },

  /**
   * Get tournament statistics for a named tournament.
   */
  async getTournamentStats(tournament: string): Promise<TournamentStats> {
    const { data } = await apiClient.get<TournamentStats>(
      `/matches/tournaments/${encodeURIComponent(tournament)}/stats`
    );
    return data;
  },

  /**
   * Get every distinct tournament name in the dataset.
   */
  async getTournaments(): Promise<string[]> {
    const { data } = await apiClient.get<string[]>("/matches/tournaments");
    return data;
  },

  /**
   * Get goal distribution by minute. Every point is currently synthetic
   * placeholder data (is_synthetic: true) — always badge it in the UI.
   */
  async getGoalDistribution(tournament?: string): Promise<GoalDistribution[]> {
    const { data } = await apiClient.get<GoalDistribution[]>(
      "/matches/analytics/goal-distribution",
      { params: { tournament } }
    );
    return data;
  },

  /**
   * Get most common scorelines (real data, not synthetic).
   */
  async getScorelineFrequency(
    tournament?: string
  ): Promise<ScorelineFrequency[]> {
    const { data } = await apiClient.get<ScorelineFrequency[]>(
      "/matches/analytics/scorelines",
      { params: { tournament } }
    );
    return data;
  },
};
