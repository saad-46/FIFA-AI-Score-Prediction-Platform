import { apiClient } from "./client";
import type {
  DashboardStats,
  FeatureImportanceResponse,
  GlobalAnalytics,
  ModelMetrics,
} from "@/types";

export const analyticsApi = {
  /**
   * Get dashboard summary stats. Richer response (recent predictions, etc.)
   * when authenticated.
   */
  async getDashboardStats(): Promise<DashboardStats> {
    const { data } = await apiClient.get<DashboardStats>(
      "/analytics/dashboard"
    );
    return data;
  },

  /**
   * Get global analytics overview (server-cached 60s). NOTE: figures reflect
   * the full historical dataset, not just the WC-only corpus.
   */
  async getGlobalAnalytics(): Promise<GlobalAnalytics> {
    const { data } = await apiClient.get<GlobalAnalytics>("/analytics/global");
    return data;
  },

  /**
   * Get model performance metrics from the training pipeline's saved reports.
   */
  async getModelMetrics(): Promise<ModelMetrics> {
    const { data } = await apiClient.get<ModelMetrics>(
      "/analytics/model-metrics"
    );
    return data;
  },

  /**
   * Get sorted feature importance for the current model.
   */
  async getFeatureImportance(): Promise<FeatureImportanceResponse> {
    const { data } = await apiClient.get<FeatureImportanceResponse>(
      "/analytics/feature-importance"
    );
    return data;
  },
};
