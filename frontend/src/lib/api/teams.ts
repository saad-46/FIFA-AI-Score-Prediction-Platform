import { apiClient } from "./client";
import type {
  Team,
  TeamStats,
  HeadToHeadStats,
  PerformanceTrend,
  PaginatedResponse,
} from "@/types";

export const teamsApi = {
  /**
   * Search teams by name
   */
  async search(query: string): Promise<Team[]> {
    const { data } = await apiClient.get<Team[]>("/teams/search", {
      params: { q: query },
    });
    return data;
  },

  /**
   * Get all teams with optional pagination
   */
  async getAll(
    page = 1,
    pageSize = 50,
    confederation?: string
  ): Promise<PaginatedResponse<Team>> {
    const { data } = await apiClient.get<PaginatedResponse<Team>>("/teams", {
      params: { page, page_size: pageSize, confederation },
    });
    return data;
  },

  /**
   * Get a single team by ID
   */
  async getById(id: string): Promise<Team> {
    const { data } = await apiClient.get<Team>(`/teams/${id}`);
    return data;
  },

  /**
   * Get team statistics
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
   * Get head-to-head stats between two teams
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
   * Get performance trend over time
   */
  async getPerformanceTrend(
    teamId: string,
    months = 24
  ): Promise<PerformanceTrend[]> {
    const { data } = await apiClient.get<PerformanceTrend[]>(
      `/teams/${teamId}/trend`,
      { params: { months } }
    );
    return data;
  },

  /**
   * Get top teams by win rate
   */
  async getTopTeams(limit = 10, tournament?: string): Promise<TeamStats[]> {
    const { data } = await apiClient.get<TeamStats[]>("/teams/top", {
      params: { limit, tournament },
    });
    return data;
  },
};
