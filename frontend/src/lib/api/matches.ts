import { apiClient } from "./client";
import type {
  Match,
  TournamentStats,
  GoalDistribution,
  ScorelineFrequency,
  PaginatedResponse,
} from "@/types";

export const matchesApi = {
  /**
   * Get paginated match history
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
   * Get a single match by ID
   */
  async getById(id: string): Promise<Match> {
    const { data } = await apiClient.get<Match>(`/matches/${id}`);
    return data;
  },

  /**
   * Get upcoming scheduled matches
   */
  async getUpcoming(limit = 10): Promise<Match[]> {
    const { data } = await apiClient.get<Match[]>("/matches/upcoming", {
      params: { limit },
    });
    return data;
  },

  /**
   * Get tournament statistics
   */
  async getTournamentStats(tournament: string): Promise<TournamentStats> {
    const { data } = await apiClient.get<TournamentStats>(
      `/matches/tournaments/${encodeURIComponent(tournament)}/stats`
    );
    return data;
  },

  /**
   * Get all available tournaments
   */
  async getTournaments(): Promise<string[]> {
    const { data } = await apiClient.get<string[]>("/matches/tournaments");
    return data;
  },

  /**
   * Get goal distribution by minute
   */
  async getGoalDistribution(tournament?: string): Promise<GoalDistribution[]> {
    const { data } = await apiClient.get<GoalDistribution[]>(
      "/matches/analytics/goal-distribution",
      { params: { tournament } }
    );
    return data;
  },

  /**
   * Get most common scorelines
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
