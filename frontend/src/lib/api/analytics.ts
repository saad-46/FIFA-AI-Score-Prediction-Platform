import { apiClient } from "./client";
import type {
  DashboardStats,
  FeatureImportanceResponse,
  GlobalAnalytics,
  ModelEvaluation,
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
   * The shipped model's headline evaluation, with its legacy predecessor
   * labelled rather than hidden.
   *
   * Prefer this over `getModelMetrics` for anything user-facing:
   * `/analytics/model-metrics` reports the **legacy v1** training metrics
   * (a 28.9% draw-boosted holdout on 376 samples), which the UI was rendering
   * as a bare "Model Accuracy".
   */
  async getModelEvaluation(): Promise<ModelEvaluation> {
    const { data } = await apiClient.get<ModelEvaluation>(
      "/analytics/model-evaluation"
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
