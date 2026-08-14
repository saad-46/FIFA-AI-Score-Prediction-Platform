import { apiClient } from "./client";
import type {
  BacktestResponse,
  BracketResponse,
  StandingsResponse,
  Wc2026TeamsResponse,
} from "@/types";

/**
 * Read-only WC2026 tournament-structure endpoints.
 *
 * Separate from `tournamentApi` (which owns the wallchart + the expensive
 * Monte Carlo simulate call) because these four are cheap cached file reads
 * with no rate limit — they can be fetched freely on page load, which is not
 * true of `/tournament/simulate`.
 */
export const wc2026Api = {
  /** All 104 matches with real results, frozen predictions, and the
   * progression wiring that drives the bracket's connectors. */
  async getBracket(): Promise<BracketResponse> {
    const { data } = await apiClient.get<BracketResponse>("/tournament/2026/bracket");
    return data;
  },

  /** Final group tables A–L, computed from real group-stage results. */
  async getStandings(): Promise<StandingsResponse> {
    const { data } = await apiClient.get<StandingsResponse>("/tournament/2026/standings");
    return data;
  },

  /** Pre-tournament Elo / FIFA ranking / group / code for the 48 teams. */
  async getTeams(): Promise<Wc2026TeamsResponse> {
    const { data } = await apiClient.get<Wc2026TeamsResponse>("/tournament/2026/teams");
    return data;
  },

  /** The frozen model's WC2026 scorecard. A historical evaluation — the UI
   * must label it as a backtest, never as a forecast. */
  async getBacktest(): Promise<BacktestResponse> {
    const { data } = await apiClient.get<BacktestResponse>("/tournament/2026/backtest");
    return data;
  },
};
