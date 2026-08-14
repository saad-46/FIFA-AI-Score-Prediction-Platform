import { apiClient } from "./client";

export interface FeedbackPayload {
  /** 1–5, or null if the visitor didn't rate. */
  rating: number | null;
  comment: string | null;
  /** Only sent when volunteered — the API never requires it. */
  email: string | null;
  page: string | null;
}

export interface FeedbackResult {
  ok: boolean;
  message: string;
}

export const feedbackApi = {
  /**
   * Submit anonymous feedback. No auth, and nothing identifying is stored
   * server-side — see the `feedback` table comment for the privacy posture.
   *
   * Rate limited to 5/min per client; a 429 surfaces through
   * `getApiErrorMessage` like any other API error.
   */
  async submit(payload: FeedbackPayload): Promise<FeedbackResult> {
    const { data } = await apiClient.post<FeedbackResult>("/feedback", payload);
    return data;
  },
};
