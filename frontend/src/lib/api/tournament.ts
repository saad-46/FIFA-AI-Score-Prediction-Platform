import { apiClient } from "./client";
import type {
  Fifa2026GroupsResponse,
  Fifa2026ScheduleResponse,
  TournamentSimulationRequest,
  TournamentSimulationResponse,
} from "@/types";

export const tournamentApi = {
  /**
   * Get the official FIFA World Cup 2026 groups (A–L, 4 teams each).
   */
  async getGroups(): Promise<Fifa2026GroupsResponse> {
    const { data } = await apiClient.get<Fifa2026GroupsResponse>(
      "/tournament/2026/groups"
    );
    return data;
  },

  /**
   * Get the official 104-fixture schedule, optionally filtered by stage/venue.
   */
  async getSchedule(filters?: {
    stage?: string;
    venue_city?: string;
  }): Promise<Fifa2026ScheduleResponse> {
    const { data } = await apiClient.get<Fifa2026ScheduleResponse>(
      "/tournament/2026/schedule",
      { params: filters }
    );
    return data;
  },

  /**
   * Run a Monte Carlo simulation of the tournament. Expensive — takes
   * roughly 5-9 seconds regardless of n_simulations (fixed pool-spawn
   * overhead dominates), so callers must design a real loading state, not a
   * generic spinner.
   */
  async simulate(
    payload: TournamentSimulationRequest = {
      use_fifa_2026_groups: true,
      n_simulations: 10000,
      use_real_results: true,
    }
  ): Promise<TournamentSimulationResponse> {
    const { data } = await apiClient.post<TournamentSimulationResponse>(
      "/tournament/simulate",
      payload,
      { timeout: 60000 }
    );
    return data;
  },
};
