import { apiClient } from "@/lib/api/client";
import type { TeamSquad } from "@/types";

export const squadApi = {
  /**
   * The whole team page in one request: 26 players, the captain and squad
   * totals. Deliberately not one call per player — a 26-card grid must not
   * become 26 round trips, and at this deployment every round trip is
   * expensive.
   */
  async getSquad(teamId: string): Promise<TeamSquad> {
    const { data } = await apiClient.get<TeamSquad>(`/teams/${teamId}/squad`);
    return data;
  },
};
