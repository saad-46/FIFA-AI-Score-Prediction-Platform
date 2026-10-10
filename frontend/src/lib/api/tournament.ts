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
   * Run a Monte Carlo simulation of the tournament. Roughly 1-2 seconds for
   * 10,000 simulations and ~12 seconds for 100,000 on the V3 engine (plus a
   * few seconds the first time a mode is requested after a restart), so
   * callers still need a real loading state. The response's `meta` says what
   * was simulated — a pre-tournament forecast or the knockout rounds given
   * the real group stage — and must be shown with the numbers.
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
