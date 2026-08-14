# V2 API Contract — for the next frontend phase

Status: **backend only.** No frontend file was modified in the phase that
produced this document. This is the contract the frontend phase can code
against.

`USE_V2_MODEL` defaults to `false`, so today every request is served by the
legacy model. Everything below describes what the frontend receives **when V2
is switched on**, so the UI can be built and reviewed before that switch.

---

## 1. The endpoint is unchanged

```
POST /api/v1/predictions/predict
Content-Type: application/json

{ "home_team": "France", "away_team": "Brazil",
  "tournament": null, "neutral_venue": false }
```

Same path, same request body, same response schema, same status codes, same
optional-auth behaviour as the legacy path. **No field was added or removed for
V2.** The frontend's existing `lib/api/predictions.ts` client continues to work
without modification — what changes is the *content* of three fields, described
below.

---

## 2. What the frontend receives

| Field | Type | V2 behaviour |
|---|---|---|
| `prediction_id` | `string` | Unchanged. Still the handle for `POST /predictions/{id}/save`. |
| `home_team`, `away_team` | `string` | Echoed back exactly as submitted, not the canonicalised internal name. |
| `predicted_home_score`, `predicted_away_score` | `int` | Integers, from the most-likely scoreline. |
| `expected_home_goals`, `expected_away_goals` | `float` | xG from the Poisson-objective regressors. |
| `home_win_probability`, `draw_probability`, `away_win_probability` | `float` | **Calibrated.** Sum to 1.0 within 1e-4 — verified per-request server-side; a violation raises rather than being silently normalised. |
| `most_likely_score` | `string` | e.g. `"1-2"`. |
| `top_scorelines` | `array` | `[{score, probability}]`, 10 entries, descending. |
| `prediction_explanation` | `object \| null` | **Now populated for V2** (was always `null` before). Real SHAP — see §3. |
| `confidence_score` | `float` | Max calibrated class probability. **See §4 before displaying this.** |
| `model_version` | `string` | `"v2-production-calibrated"` (or `"v2-calibrated"` if the backtest bundle is configured). Use this to distinguish V2 from legacy responses. |
| `insights` | `array` | Rule-based text insights. Unchanged shape. |
| `head_to_head` | `object \| null` | Unchanged shape. |
| `created_at` | `datetime` | Unchanged. |

### Representative V2 response

```json
{
  "prediction_id": "…",
  "home_team": "France",
  "away_team": "Brazil",
  "predicted_home_score": 0,
  "predicted_away_score": 1,
  "expected_home_goals": 0.768,
  "expected_away_goals": 1.013,
  "home_win_probability": 0.269,
  "draw_probability": 0.338,
  "away_win_probability": 0.393,
  "most_likely_score": "0-1",
  "top_scorelines": [
    {"score": "0-1", "probability": 0.1707},
    {"score": "0-0", "probability": 0.1685}
  ],
  "prediction_explanation": {
    "predicted_outcome": "away_win",
    "confidence": 0.4429,
    "top_positive_features": [
      {"feature": "wc_tournaments_diff",
       "readable_name": "Tournaments played difference",
       "impact": 0.1965}
    ],
    "top_negative_features": [
      {"feature": "home_form_ga_5",
       "readable_name": "Home goals conceded, last 5",
       "impact": -0.1659}
    ]
  },
  "confidence_score": 0.4429,
  "model_version": "v2-production-calibrated",
  "insights": [ … ],
  "head_to_head": { … },
  "created_at": "2026-08-13T…"
}
```

---

## 3. `prediction_explanation` — real SHAP, and its limits

Shape is **identical** to the legacy `PredictionExplanation` schema, so the
existing `shap-explanation.tsx` component renders it without changes.

```
prediction_explanation
├── predicted_outcome        "home_win" | "draw" | "away_win"
├── confidence               float, 0-1
├── top_positive_features[]  ≤5, sorted by |impact| desc
│     ├── feature            raw model feature name
│     ├── readable_name      display label, always present
│     └── impact             signed float, > 0
└── top_negative_features[]  ≤5, impact < 0
```

**What `impact` means:** a SHAP contribution in **log-odds space** for the
predicted class, computed by `shap.TreeExplainer` against the exact feature
vector that produced the prediction. Values are not percentages and do not sum
to the probability — render them as *relative* bar lengths, which is what the
existing component already does.

**Honest limits the UI should respect:**

- Explanations describe the **predicted class only**, not all three outcomes.
- **Scoreline distribution is not SHAP-explainable.** `most_likely_score` and
  `top_scorelines` come from a closed-form Poisson transformation of the two xG
  values, not a learned model — there are no features to attribute. Don't build
  UI implying otherwise.
- xG attributions exist but live in a **different space** (log-expected-goals)
  and are deliberately not merged into this block. They are not currently
  exposed over the API; ask if the UI needs them.
- `prediction_explanation` may be `null` or `{}` if SHAP failed. Treat it as
  optional — it is omitted rather than fabricated.

---

## 4. `confidence_score` — do not feature it prominently yet

The V2 probabilities are substantially better calibrated than before
(chronological ECE 0.228 → 0.111), but calibration is **not perfect**, and the
residual error is *under*-confidence in the mid range: predictions stated
around 55% came true about 72% of the time in the WC2026 backtest.

Under-confidence is the safe direction — the model understates rather than
overstates what it knows — but a large "44% CONFIDENCE" readout would still
mislead. Recommendation for this phase: keep `confidence_score` available in
the payload, use it for internal ordering/thresholds if useful, and hold off on
a prominent confidence indicator until it has been validated against a second
tournament.

---

## 5. Rate limiting — new response the frontend must handle

Both expensive endpoints are now rate limited. Counters are shared across
workers, so the limit is a real per-client limit.

| Endpoint | Default limit | Notes |
|---|---|---|
| `POST /api/v1/predictions/predict` | 30/min per client | One request per form submission; ample headroom for exploring matchups. |
| `POST /api/v1/tournament/simulate` | 5/min per client | Several seconds of CPU per call. |

Authenticated callers are limited **per account**; anonymous callers **per IP**
(read from `X-Forwarded-For`, so users behind one office IP aren't lumped
together once signed in).

**On exceeding the limit — `429 Too Many Requests`:**

```
Retry-After: 42
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1786000000

{"detail": "Rate limit exceeded for this endpoint (30 requests per 60s). Retry in 42s."}
```

The frontend should handle 429 explicitly — surface `detail` and use
`Retry-After` to disable the submit button for that many seconds. The existing
`getApiErrorMessage()` helper already surfaces FastAPI's `detail`, so the
minimum viable handling is a toast; a countdown is nicer.

---

## 6. Tournament metadata available for the bracket phase

Already in the database and queryable — **no schema work needed** for the
bracket UI:

- `wc2026_tournament_graph` — 104 rows, one per match: `match_number`, `stage`,
  `is_knockout`, `home_source_type`/`home_source_match`,
  `away_source_type`/`away_source_match`, `feeds_winner_to`, `feeds_loser_to`.
  This is the full progression model (group → R32 → R16 → QF → SF → final, plus
  the bronze-final branch off the semi-final losers).
- `matches_v2` — all 104 WC2026 fixtures with `match_number`, dates, venues,
  real scores, and `stage`.
- `teams_v2` — 48 WC2026 teams with `fifa_code`, `wc2026_group`,
  `elo_rating_pre_wc2026`, `fifa_ranking_pre_wc2026`.

**Not yet exposed over the API.** The bracket phase will need new read-only
endpoints (e.g. `GET /tournament/2026/bracket`); the data behind them is
already validated and in place.

---

## 7. Two models — which one the frontend is talking to

| `model_version` | Meaning |
|---|---|
| `v2-production-calibrated` | Trained through 2026, for predicting **future** matches. The default when V2 is on. Its 2026 predictions are in-sample — never present them as accuracy. |
| `v2-calibrated` | Backtest bundle, frozen at 2022. The **only** source of quotable WC2026 accuracy (60.6%). |
| anything else | Legacy model. |

If the UI ever displays accuracy figures, they must come from the backtest
model's published numbers, not from whatever bundle is currently serving.
