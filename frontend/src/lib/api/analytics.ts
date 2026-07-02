import { apiClient } from "./client";
import type { DashboardStats } from "@/types";

export interface GlobalAnalytics {
  total_matches: number;
  total_goals: number;
  avg_goals_per_match: number;
  home_win_rate: number;
  draw_rate: number;
  away_win_rate: number;
  goals_by_year: Array<{ year: number; goals: number; matches: number }>;
  top_tournaments: Array<{ tournament: string; matches: number }>;
}

export const analyticsApi = {
  /**
   * Get dashboard summary stats
   */
  async getDashboardStats(): Promise<DashboardStats> {
    const { data } = await apiClient.get<DashboardStats>(
      "/analytics/dashboard"
    );
    return data;
  },

  /**
   * Get global analytics overview
   */
  async getGlobalAnalytics(): Promise<GlobalAnalytics> {
    const { data } = await apiClient.get<GlobalAnalytics>("/analytics/global");
    return data;
  },

  /**
   * Get model performance metrics
   */
  async getModelMetrics(): Promise<{
    accuracy: number;
    mae: number;
    rmse: number;
    last_trained: string;
    training_samples: number;
    model_version: string;
  }> {
    const { data } = await apiClient.get("/analytics/model-metrics");
    return data;
  },
};
