import { apiClient } from "./client";
import type {
  PredictionRequest,
  PredictionResult,
  SavedPrediction,
  PaginatedResponse,
} from "@/types";

export const predictionsApi = {
  /**
   * Run AI prediction for a match
   */
  async predict(payload: PredictionRequest): Promise<PredictionResult> {
    const { data } = await apiClient.post<PredictionResult>(
      "/predictions/predict",
      payload
    );
    return data;
  },

  /**
   * Save a prediction to the user's account
   */
  async save(predictionId: string): Promise<SavedPrediction> {
    const { data } = await apiClient.post<SavedPrediction>(
      `/predictions/${predictionId}/save`
    );
    return data;
  },

  /**
   * Get all saved predictions for the authenticated user
   */
  async getSaved(
    page = 1,
    pageSize = 20
  ): Promise<PaginatedResponse<SavedPrediction>> {
    const { data } = await apiClient.get<PaginatedResponse<SavedPrediction>>(
      "/predictions/saved",
      { params: { page, page_size: pageSize } }
    );
    return data;
  },

  /**
   * Delete a saved prediction
   */
  async deleteSaved(id: string): Promise<void> {
    await apiClient.delete(`/predictions/saved/${id}`);
  },

  /**
   * Get prediction accuracy stats for the authenticated user
   */
  async getAccuracyStats(): Promise<{
    total: number;
    correct: number;
    accuracy: number;
  }> {
    const { data } = await apiClient.get("/predictions/accuracy");
    return data;
  },
};
