## FIFA World Cup 2026 reference data

Source of truth: the official FIFA World Cup 2026 Match Schedule wallchart PDF
provided by the user (single-page infographic, all times printed as ET).
Extracted 2026-07-02.

- `groups.json` — the 12 groups (A-L), 4 teams each, 48 teams total, with
  3-letter codes as printed on the chart and full country names.
- `schedule.json` — all 104 matches: match_number, date (ISO), kickoff_time_et,
  venue_city, stage (group_stage / round_of_32 / round_of_16 / quarter_final /
  semi_final / third_place / final), group (group-stage only), home_team,
  away_team. Knockout-round participants not yet determined are encoded as
  `W##` (winner of match ##) or `L##` (loser of match ##), matching the
  wallchart's own placeholder notation for Round of 32 through Semi-finals.
  The Bronze Final (103) and Final (104) print literal "BRONZE FINAL"/"FINAL"
  text on the chart rather than W/L codes; `L101`/`L102` and `W101`/`W102`
  are inferred from tournament structure, not read directly off the chart.
- `venues.json` — the 16 host cities and their region groupings, as printed.

### Documented assumptions / known gaps

- **No stadium names.** The wallchart labels venues by city only (e.g.
  "New York New Jersey"), never by specific stadium (e.g. MetLife Stadium).
  Stadium names are intentionally NOT included here to avoid inventing
  unsupported facts — see `KNOWN_ASSUMPTIONS.md` at the repo root.
- **All kickoff times are Eastern Time (ET)** as printed; no timezone
  conversion has been applied per venue.
- Match 6 (Vancouver, AUS v TUR, 2026-06-13) is genuinely listed as a
  00:00 ET kickoff on the source chart.
