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
   * The 48 teams at the 2026 World Cup, alphabetically.
   *
   * Use this for the team directory rather than `getTopTeams`, which returns a
   * win-rate leaderboard capped at `limit` (the directory used to render 20 of
   * 48) and draws from a table that also contains non-national entities from
   * the legacy data seed.
   *
   * The server orders with Postgres' locale collation, which sorts accents
   * naturally ("Côte d'Ivoire" between Congo DR and Croatia). Re-sorting on the
   * client with a default comparator would push accented names to the end, so
   * preserve this order or re-sort with `localeCompare`.
   */
  async getWc2026Teams(): Promise<Team[]> {
    const { data } = await apiClient.get<Team[]>("/teams/wc2026");
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
