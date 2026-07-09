import { apiClient } from "./client";
import type {
  AccuracyStats,
  PredictionRequest,
  PredictionResult,
  SavedPrediction,
} from "@/types";

export const predictionsApi = {
  /**
   * Run AI prediction for a match. Public endpoint — no auth required.
   */
  async predict(payload: PredictionRequest): Promise<PredictionResult> {
    const { data } = await apiClient.post<PredictionResult>(
      "/predictions/predict",
      payload
    );
    return data;
  },

  /**
   * Save a prediction to the user's account. Requires auth.
   */
  async save(predictionId: string): Promise<SavedPrediction> {
    const { data } = await apiClient.post<SavedPrediction>(
      `/predictions/${predictionId}/save`
    );
    return data;
  },

  /**
   * Get all saved predictions for the authenticated user.
   * Returns a plain array — this endpoint is NOT paginated despite taking
   * page/page_size params (they just control offset/limit server-side).
   */
  async getSaved(page = 1, pageSize = 20): Promise<SavedPrediction[]> {
    const { data } = await apiClient.get<SavedPrediction[]>(
      "/predictions/saved",
      { params: { page, page_size: pageSize } }
    );
    return data;
  },

  /**
   * Delete a saved prediction. Requires auth.
   */
  async deleteSaved(id: string): Promise<void> {
    await apiClient.delete(`/predictions/saved/${id}`);
  },

  /**
   * Get prediction accuracy stats for the authenticated user.
   */
  async getAccuracyStats(): Promise<AccuracyStats> {
    const { data } = await apiClient.get<AccuracyStats>(
      "/predictions/accuracy"
    );
    return data;
  },
};
