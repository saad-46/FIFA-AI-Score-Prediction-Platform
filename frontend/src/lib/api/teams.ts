import { apiClient } from "./client";
import type { Team, TeamStats, HeadToHeadStats, PerformanceTrendPoint } from "@/types";

export const teamsApi = {
  /**
   * Search teams by name (case-insensitive substring match). Min 2 chars.
   */
  async search(query: string): Promise<Team[]> {
    const { data } = await apiClient.get<Team[]>("/teams/search", {
      params: { q: query },
    });
    return data;
  },

  /**
   * Get a single team by ID.
   */
  async getById(id: string): Promise<Team> {
    const { data } = await apiClient.get<Team>(`/teams/${id}`);
    return data;
  },

  /**
   * Get team statistics for a given team.
   */
  async getStats(
    teamId: string,
    tournament?: string,
    years?: number
  ): Promise<TeamStats> {
    const { data } = await apiClient.get<TeamStats>(`/teams/${teamId}/stats`, {
      params: { tournament, years },
    });
    return data;
  },

  /**
   * Get head-to-head stats between two teams.
   */
  async getHeadToHead(
    homeTeamId: string,
    awayTeamId: string
  ): Promise<HeadToHeadStats> {
    const { data } = await apiClient.get<HeadToHeadStats>(
      `/teams/head-to-head`,
      { params: { home_team_id: homeTeamId, away_team_id: awayTeamId } }
    );
    return data;
  },

  /**
   * Get monthly-aggregated performance trend over time.
   */
  async getPerformanceTrend(
    teamId: string,
    months = 24
  ): Promise<PerformanceTrendPoint[]> {
    const { data } = await apiClient.get<PerformanceTrendPoint[]>(
      `/teams/${teamId}/trend`,
      { params: { months } }
    );
    return data;
  },

  /**
   * Get top teams by win rate (minimum 2 matches played to qualify).
   */
  async getTopTeams(limit = 10, tournament?: string): Promise<TeamStats[]> {
    const { data } = await apiClient.get<TeamStats[]>("/teams/top", {
      params: { limit, tournament },
    });
    return data;
  },
};
