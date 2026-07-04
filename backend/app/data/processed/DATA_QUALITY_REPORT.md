# Data Quality Report — Wave 1 Data Engineering

FIFA World Cup 2026 AI Prediction Platform. Generated 2026-07-03.

Source files (repo root, `D:\Projects\fifa score predictor\`):
1. `FIFA_World_Cup_Matches(b42022).xlsx` (sheet "Cleaned Data", 330 rows) — WC matches 2002-2022
2. `matches.csv.xlsx` (sheet "matches", 89 rows) — 2026 matches, IDs
3. `matches_detailed.csv.xlsx` (sheet "matches_detailed", 89 rows) — 2026 matches, names
4. `match_team_stats.csv.xlsx` (sheet "match_team_stats", 132 rows) — 2026 per-match team stats
5. `teams(group_rank).csv.xlsx` (sheet "teams", 48 rows) — 2026 team roster
6. `tournament_stages.csv.xlsx` (sheet "tournament_stages", 7 rows) — stage lookup
7. `wc_2026_fixtures(b4ro32).xlsx` (sheet "wc_2026_fixtures", 104 rows) — official fixture template

Trusted reference (not modified): `backend/app/data/fifa_2026/schedule.json`, `groups.json`, `venues.json`.

---

## (a) Schema / quality findings per source file

### File #1 — `FIFA_World_Cup_Matches(b42022).xlsx` ("Cleaned Data", 330 rows)
- Columns: `Year(int64), Team 1(str), Team 2(str), Stage(str), Date(str "DD-Month-YYYY"), Team1 Goals(int64), Team2 Goals(int64), Venue(str), Winner(str), Winning Margin(int64)`.
- **No nulls** in any column, **no duplicate rows** (exact or on `Year+Team1+Team2+Date`).
- `Date` is a free-text string (`"31-May-2002"`, `"01-June-2002"`) — parses cleanly with `pd.to_datetime(..., format='%d-%B-%Y')`; converted to ISO 8601.
- **Row completeness gap**: each WC tournament should have 64 matches (48 group + 8 R16 + 4 QF + 2 SF + 1 third-place + 1 final), but every single year in this dataset has only **55 rows** — missing roughly 6-9 group-stage matches and, for 2002, the entire third-place match. This is a pre-existing gap in the widely-used Kaggle-derived dataset itself, not introduced by us. We did **not** fabricate the missing rows; they are simply absent from the merged output for those tournaments.
  - Per-year stage breakdown confirms the shortfall is concentrated in Group Stage (41-42 rows instead of 48).
- Stage vocabulary: `Final, Group Stage, Quarter-finals, Round Of 16, Semi-finals, Third-place Match` — all map cleanly onto schedule.json's vocabulary (see section b).
- Team-name spellings use the naming convention of each historical era (e.g. "Czech Republic" not "Czechia", "Turkey" not "Türkiye", "United States" not "USA", "Ivory Coast" not "Côte d'Ivoire", "Iran" not "IR Iran") — reconciled, see mapping table.

### File #2 — `matches.csv.xlsx` ("matches", 89 rows)
- Columns: `match_id(int), date(datetime), stage_id(int), home_team_id(int), away_team_id(float — nullable), home_score(float), away_score(float), status(str), home_xg(float), away_xg(float), player_of_the_match_id(float)`.
- No duplicate `match_id`.
- 13 rows have null `home_score/away_score/home_xg/away_xg/player_of_the_match_id` — these are the 13 `status == "Scheduled"` (not yet played) matches, which is expected/correct, not a defect.
- 1 row (`match_id 89`) has a null `away_team_id` — this is the Round-of-16 slot for the still-undetermined opponent of Canada (TBD advancement), correctly represented as null rather than a placeholder ID.
- `status` values: `Completed` (76), `Scheduled` (13).

### File #3 — `matches_detailed.csv.xlsx` ("matches_detailed", 89 rows)
- Columns: `match_id, date, stage_name, home_team_name, home_fifa_code, away_team_name, away_fifa_code, home_score, away_score, status, home_xg, away_xg, home_goalkeeper, away_goalkeeper, player_of_the_match_name`.
- Same 13-row null pattern as file #2 for score/xg/goalkeeper/player fields (unplayed matches) — consistent.
- The one TBD opponent (match 89) is represented as the literal string `"Unknown"` / fifa_code `"UNK"` rather than null — a reasonable convention, handled explicitly in our merge (left in place, not treated as a real team).
- **Encoding bug** (mojibake): 3 team names are double-UTF-8-encoded: `"TÃ¼rkiye"` (should be `"Türkiye"`), `"CuraÃ§ao"` (should be `"Curaçao"`), `"CÃ´te d'Ivoire"` (should be `"Côte d'Ivoire"`). Same bug appears identically in files #5 and #7 (see below) — fixed in our canonical output.
- Stage vocabulary: `Group Stage, Round of 32, Round of 16` (tournament is mid-competition; later stages not yet reached).

### File #2 vs File #3 cross-check (same 89 "real" 2026 matches)
Merged on `match_id` and compared every shared field: **zero disagreements** found on `date`, `home_score`, `away_score`, `home_xg`, `away_xg`, `status`. Team IDs in file #2 resolve via file #5's `team_id → team_name / fifa_code` to the exact same names/codes recorded directly in file #3 for all 89 rows (zero mismatches). The two files are fully redundant/consistent on overlapping fields, as expected — confirms file #3's home_team_name/away_team_name and file #2's home_team_id/away_team_id are two encodings of the same underlying data.

### File #4 — `match_team_stats.csv.xlsx` ("match_team_stats", 132 rows)
- Columns: `match_id, team_id, possession_pct, total_shots, shots_on_target, corners, fouls, offsides, saves, player_of_the_match`.
- 132 rows = 66 matches × 2 teams. No duplicate `(match_id, team_id)` pairs.
- `player_of_the_match` null for 66/132 rows (the non-POTM team row in each pair) — expected.
- **Coverage gap**: only 66 of the 76 `Completed` matches (per file #2) have team-stats rows. **10 completed matches have no stats at all**: `match_id ∈ {53, 54, 55, 57, 58, 59, 60, 61, 62, 63}`. Not fabricated — left absent in the normalized output.
- `possession_pct` does not always sum to exactly 100 per match (22 of 66 matches sum to something other than 100, e.g. 81–93) — this is realistic/expected for real match-stats data (rounding, stoppage variance) and was **not** "corrected," since doing so would mean altering real recorded values.

### File #5 — `teams(group_rank).csv.xlsx` ("teams", 48 rows)
- Columns: `team_id, team_name, fifa_code, group_letter, confederation, fifa_ranking_pre_tournament, elo_rating`.
- No nulls, no duplicate `team_id`/`team_name`/`fifa_code`. Exactly 12 groups (A–L) of 4 teams each.
- **Encoding bug** (mojibake, same root cause as file #3/#7): `team_name` values `"TÃ¼rkiye"`, `"CuraÃ§ao"`, `"CÃ´te d'Ivoire"` are corrupted double-encoded UTF-8. **Fixed** in `teams_reference.csv` and throughout the merged output to `"Türkiye"`, `"Curaçao"`, `"Côte d'Ivoire"`.
- Cross-checked against `groups.json` (trusted reference): **zero group-letter (A–L) assignment mismatches** and **zero fifa_code set mismatches** across all 48 teams (see section d). Only difference is display-name convention (see mapping table) — e.g. file #5 says "South Korea" / groups.json says "Korea Republic"; file #5 says "Bosnia and Herzegovina" / groups.json says "Bosnia & Herzegovina". These are not treated as errors — file #5's spelling was used as the canonical spelling per task instructions (canonical table is anchored on file #5), while groups.json/schedule.json are left untouched per instructions.

### File #6 — `tournament_stages.csv.xlsx` ("tournament_stages", 7 rows)
- Clean lookup table, no issues: `stage_id 1-7` → `Group Stage, Round of 32, Round of 16, Quarter-finals, Semi-finals, Third-place match, Final` with `is_knockout` flag. Used to independently verify file #2's `stage_id` resolves to the same stage as file #3's `stage_name` for every one of the 89 rows (zero mismatches).

### File #7 — `wc_2026_fixtures(b4ro32).xlsx` ("wc_2026_fixtures", 104 rows)
- Columns: `group, stage, team1, team2, venue, city, country, date, kickoff_et, team1_confederation, team1_fifa_rank, team1_coach, team2_confederation, team2_fifa_rank, team2_coach`.
- No duplicate rows. `group` and the `*_confederation/_fifa_rank/_coach` columns are null for the 32 knockout-stage rows beyond Round of 32 (Round of 16 onward) — expected, since this is the **pre-tournament fixture template**: group-stage matches have real teams, but Round-of-32-onward slots are represented as bracket placeholders (`"1A"`, `"2B"`, `"QF1"`, `"SF1"`, `"Best 3rd #1"`, `"Finalist 1"`, etc., 65 distinct placeholder tokens) rather than resolved team names, since this file predates the tournament's actual group-stage results.
- Team-name variants that are real spelling differences (not placeholders): `"Cape Verde"` (file #5 says `"Cabo Verde"`), `"DR Congo"` (file #5 says `"Congo DR"`), `"Iran"` (file #5 says `"IR Iran"`), `"Ivory Coast"` (file #5 says `"Côte d'Ivoire"`) — all reconciled in the mapping table.
- Same mojibake encoding bug as files #3/#5 for `Türkiye`/`Curaçao` — fixed.
- `venue`/`city` use literal stadium-suburb municipality names (e.g. "Arlington", "East Rutherford", "Foxborough", "Inglewood"/"Pasadena") rather than the metro-area labels used by `venues.json`/`schedule.json` ("Dallas", "New York New Jersey", "Boston", "Los Angeles") — this is a labeling-convention difference explained by `venues.json`'s own comment (wallchart uses city/region labels, not stadium municipality), not a factual conflict.
- For group-stage rows, all 48 team→group assignments agree with file #5 (zero mismatches, after normalizing the 4 real name variants above).
- `fifa_rank` values in file #7 **differ** from `fifa_ranking_pre_tournament` in file #5 for **34 of 48 teams** (e.g. France: 1 in file7 vs 3 in file5; Argentina: 3 vs 1; Mexico: 15 vs 14). This looks like two different ranking snapshots/sources (file #7's ranks appear to be an earlier or differently-dated FIFA ranking pull than file #5's). Per task instructions, `teams_reference.csv` uses file #5's `fifa_ranking_pre_tournament` only; file #7's ranks were not merged in and are **not** used anywhere in the outputs. Flagging this in case a later wave wants to reconcile which snapshot is authoritative.

---

## (b) Canonical team-name mapping table

Canonical name = file #5's (mojibake-fixed) spelling for all 48 2026-tournament teams. Historical-only teams (2002-2022, not in the 48) keep their own name as canonical **unless** the same nation appears under 2+ spellings somewhere across files #1/#3/#5/#7, in which case the modern/2026-era spelling was adopted. 79 distinct real team-name tokens were found across files #1, #3, #5, #7 (after excluding 65 file #7 bracket-placeholder tokens, e.g. `"1A"`, `"QF1"`, `"Best 3rd #1"`, and file #3's `"Unknown"` TBD placeholder).

**7 raw variants required normalization** (all others already matched their canonical form):

| raw variant (source)                  | canonical name   | fifa_code |
|----------------------------------------|------------------|-----------|
| Cape Verde (file #7)                   | Cabo Verde       | CPV       |
| DR Congo (file #7)                     | Congo DR         | COD       |
| Czech Republic (file #1)               | Czechia          | CZE       |
| Ivory Coast (file #7)                  | Côte d'Ivoire    | CIV       |
| Iran (file #7)                         | IR Iran          | IRN       |
| Turkey (file #1)                       | Türkiye          | TUR       |
| United States (file #1)                | USA              | USA       |

Plus 3 **encoding-only** fixes applied identically wherever the corrupted string appeared (files #3, #5, #7): `TÃ¼rkiye → Türkiye`, `CuraÃ§ao → Curaçao`, `CÃ´te d'Ivoire → Côte d'Ivoire` (folded into the same canonical targets as above).

**Full 79-row mapping table** (unchanged rows included for completeness — raw variant equals canonical name):

| raw variant | canonical name | fifa_code |
|---|---|---|
| Algeria | Algeria | ALG |
| Angola | Angola | ANG |
| Argentina | Argentina | ARG |
| Australia | Australia | AUS |
| Austria | Austria | AUT |
| Belgium | Belgium | BEL |
| Bosnia and Herzegovina | Bosnia and Herzegovina | BIH |
| Brazil | Brazil | BRA |
| Cabo Verde | Cabo Verde | CPV |
| Cape Verde | **Cabo Verde** | CPV |
| Cameroon | Cameroon | CMR |
| Canada | Canada | CAN |
| Chile | Chile | CHI |
| China | China | CHN |
| Colombia | Colombia | COL |
| Congo DR | Congo DR | COD |
| DR Congo | **Congo DR** | COD |
| Costa Rica | Costa Rica | CRC |
| Croatia | Croatia | CRO |
| Curaçao (incl. mojibake `CuraÃ§ao`) | Curaçao | CUW |
| Czech Republic | **Czechia** | CZE |
| Czechia | Czechia | CZE |
| Côte d'Ivoire (incl. mojibake `CÃ´te d'Ivoire`) | Côte d'Ivoire | CIV |
| Ivory Coast | **Côte d'Ivoire** | CIV |
| Denmark | Denmark | DEN |
| Ecuador | Ecuador | ECU |
| Egypt | Egypt | EGY |
| England | England | ENG |
| France | France | FRA |
| Germany | Germany | GER |
| Ghana | Ghana | GHA |
| Greece | Greece | GRE |
| Haiti | Haiti | HAI |
| Honduras | Honduras | HON |
| IR Iran | IR Iran | IRN |
| Iran | **IR Iran** | IRN |
| Iceland | Iceland | ISL |
| Iraq | Iraq | IRQ |
| Italy | Italy | ITA |
| Japan | Japan | JPN |
| Jordan | Jordan | JOR |
| Mexico | Mexico | MEX |
| Morocco | Morocco | MAR |
| Netherlands | Netherlands | NED |
| New Zealand | New Zealand | NZL |
| Nigeria | Nigeria | NGA |
| North Korea | North Korea | PRK |
| Norway | Norway | NOR |
| Panama | Panama | PAN |
| Paraguay | Paraguay | PAR |
| Peru | Peru | PER |
| Poland | Poland | POL |
| Portugal | Portugal | POR |
| Qatar | Qatar | QAT |
| Republic of Ireland | Republic of Ireland | IRL |
| Russia | Russia | RUS |
| Saudi Arabia | Saudi Arabia | KSA |
| Scotland | Scotland | SCO |
| Senegal | Senegal | SEN |
| Serbia | Serbia | SRB |
| Serbia and Montenegro | Serbia and Montenegro | SCG |
| Slovakia | Slovakia | SVK |
| Slovenia | Slovenia | SVN |
| South Africa | South Africa | RSA |
| South Korea | South Korea | KOR |
| Spain | Spain | ESP |
| Sweden | Sweden | SWE |
| Switzerland | Switzerland | SUI |
| Togo | Togo | TOG |
| Trinidad and Tobago | Trinidad and Tobago | TRI |
| Tunisia | Tunisia | TUN |
| Turkey | **Türkiye** | TUR |
| Türkiye (incl. mojibake `TÃ¼rkiye`) | Türkiye | TUR |
| USA | USA | USA |
| United States | **USA** | USA |
| Ukraine | Ukraine | UKR |
| Uruguay | Uruguay | URU |
| Uzbekistan | Uzbekistan | UZB |
| Wales | Wales | WAL |

Note: `South Korea` (file #5/#3 spelling) vs `Korea Republic` (schedule.json/groups.json spelling), and `Bosnia and Herzegovina` (file #5/#3) vs `Bosnia & Herzegovina` (schedule.json/groups.json) are **display-convention differences only** — both refer to the identical team/fifa_code (KOR, BIH) and both resolve to the identical group letter. Since `teams_reference.csv` is anchored on file #5 per task instructions, file #5's spelling ("South Korea", "Bosnia and Herzegovina") was kept as canonical; schedule.json/groups.json were left untouched as instructed.

Excluded as non-team placeholder tokens (file #7 knockout-bracket slots, not normalized): `1A..1L`, `2A..2L`, `QF1..QF8`, `SF1..SF4`, `R32 W1..R32 W16`, `Best 3rd #1..#8`, `3rd Place`, `Finalist 1`, `Finalist 2` (65 tokens); and file #3's `"Unknown"`/`"UNK"` TBD-opponent placeholder for the one still-undetermined Round-of-16 slot (match_id 89).

---

## (c) Duplicates / inconsistencies found and resolution

1. **Mojibake encoding corruption** in files #3, #5, #7 (`Türkiye`, `Curaçao`, `Côte d'Ivoire` double-encoded) — **fixed** by re-mapping the corrupted byte sequences to the correct UTF-8 strings before any further processing, applied identically to every occurrence.
2. **4 real spelling variants** in file #7 not present anywhere else (`Cape Verde`, `DR Congo`, `Iran`, `Ivory Coast`) — **resolved** onto file #5's canonical spelling via the mapping table above.
3. **3 real spelling variants** in file #1 for teams that also appear in the 2026 field under a different (modern) name (`Czech Republic`→`Czechia`, `Turkey`→`Türkiye`, `United States`→`USA`) — **resolved** onto the modern/2026 spelling so the same nation is represented identically whether it appears in 2002-2022 or 2026 rows.
4. **File #1 missing ~9 matches per tournament** (55 rows/year instead of 64) — **not fixed** (would require fabricating unknown match data); documented as a known limitation of the source dataset. The gap is concentrated in Group Stage rows and, for 2002 only, the Third-place match.
5. **File #4 missing stats for 10 completed matches** (`match_id 53-55, 57-63`) — **not fixed** (no fabrication); these 10 matches simply have no corresponding rows in `match_team_stats.csv`.
6. **File #2 vs #3 comparison** — **zero disagreements** found across all 89 shared rows on date/scores/xG/status; the two files are fully consistent duplicates of each other on overlapping fields (file #2 = IDs/xG, file #3 = names/codes/goalkeepers).
7. **No duplicate rows** found in any of the 7 source files (checked full-row duplicates and natural-key duplicates: `Year+Team1+Team2+Date` for file #1, `match_id` for files #2/3, `match_id+team_id` for file #4, `team_id`/`team_name`/`fifa_code` for file #5, full-row for file #7).
8. **Surrogate match_id** synthesized for the 330 pre-2026 rows (file #1 has no match_id): `hist_<sha1("{year}|{home_team_canon}|{away_team_canon}|{date_iso}")[:10]>`. Verified zero collisions across all 330 rows.
9. **fifa_ranking_pre_tournament (file #5) vs fifa_rank (file #7)** disagree for 34/48 teams — not reconciled; only file #5's ranking is carried into `teams_reference.csv` per task instructions (see file #7 discussion in section a).

---

## (d) Schedule / groups cross-validation (schedule.json & groups.json vs file #7 & file #5)

`schedule.json`/`groups.json` were **not modified** — the following is a read-only comparison report.

### Groups (`groups.json` vs file #5, 48 teams / 12 groups)
- **Zero discrepancies.** Every one of the 48 teams' `fifa_code → group_letter` assignment in file #5 matches `groups.json` exactly. Every fifa_code set matches exactly (no missing/extra teams in either direction).
- Only difference: display-name spelling convention for 2 teams (informational, not an error) — `KOR`: file #5 "South Korea" vs groups.json "Korea Republic"; `BIH`: file #5 "Bosnia and Herzegovina" vs groups.json "Bosnia & Herzegovina". Also the 3 mojibake-corrupted names in file #5 (`TUR`, `CUW`, `CIV`) which decode to the same names groups.json already has correctly.

### Schedule counts (`schedule.json` vs file #7, 104 matches each)
- Total match count: **104 = 104**, matches.
- Per-stage counts: **identical** at every stage — `group_stage` 72=72, `round_of_32` 16=16, `round_of_16` 8=8, `quarter_final` 4=4, `semi_final` 2=2, `third_place` 1=1, `final` 1=1.

### Group-stage fixtures (72 matches): teams, dates, discrepancies
Matchups (which two teams play) agree 100% between the two sources (all 72 pairings identical), but **8 of 72 group-stage matches have a different date** in `schedule.json` vs file #7:

| Group | Teams | schedule.json date | file #7 date |
|---|---|---|---|
| B | QAT vs CAN | 2026-06-18 | 2026-06-19 |
| C | HAI vs BRA | 2026-06-19 | 2026-06-19 (same date, but paired against a different opponent that matchday — see note) |
| C | MAR vs SCO | 2026-06-19 | 2026-06-19 (same date; schedule.json pairs SCO-MAR, file #7 pairs BRA-SCO and MAR-HAI on 6/19 instead) |
| D | PAR vs TUR | 2026-06-18 | 2026-06-20 |
| F | NED vs TUN | 2026-06-25 | 2026-06-26 |
| F | SWE vs JPN | 2026-06-25 | 2026-06-26 |
| J | AUT vs JOR | 2026-06-16 | 2026-06-17 |
| J | ALG vs JOR | 2026-06-22 | 2026-06-23 |

Detail on the **Group C anomaly** (the only group where the actual pairing on a given matchday differs, not just the date): on matchday 2 (2026-06-19), `schedule.json` has **Brazil vs Haiti** and **Scotland vs Morocco**, while file #7 has **Brazil vs Scotland** and **Morocco vs Haiti** on that same date. This is a genuine matchup discrepancy, not just a date shift — worth flagging explicitly for a later wave to resolve against an authoritative source (e.g. FIFA.com) since these are two different sets of results for "matchday 2, Group C."

All other groups (A, E, G, H, I, K, L) agree exactly on both teams and dates for all 3 matchdays.

### Venue/city — group stage
File #7 uses literal stadium-suburb municipality names (e.g. "East Rutherford", "Foxborough", "Arlington", "Inglewood"/"Pasadena") where `schedule.json`/`venues.json` use metro-area labels ("New York New Jersey", "Boston", "Dallas", "Los Angeles"). After normalizing city names via `venues.json`'s own region/city mapping, no further group-stage venue discrepancies were found beyond the date-shifted matches listed above (each date-shifted match's venue moved along with its date in both sources consistently).

### Knockout stage (Round of 32 onward): resolved-vs-template comparison
`schedule.json` reflects the **actual, already-resolved** Round of 32 matchups (the tournament has completed its group stage as of 2026-07-03), while file #7 still shows the **pre-tournament bracket template** with placeholder slots (`"1A"`, `"2B"`, `"Best 3rd #1"`, etc.) since it was generated before group results were known. We verified `schedule.json`'s Round-of-32 pairings are **internally correct**: independently recomputing group standings (points, then goal difference, then goals-for) from the completed group-stage match results in file #3 reproduces exactly the same 12 group winners, 12 runners-up, and 8 best-third-place teams that appear in `schedule.json`'s Round of 32 fixture list. This is not treated as a discrepancy — it is expected divergence between a template and its resolved instantiation.

However, independent of team-slot resolution, the following **date and venue-count discrepancies** were found between `schedule.json` and file #7's per-stage structure:

**Round of 32** (16 matches each):
- Date spread differs: schedule.json spans 2026-06-28 → 2026-07-03 (2/2/3/3/3/3 matches per day); file #7 spans 2026-06-28 → 2026-07-04 (2/2/2/2/2/4/2 matches per day).
- Venue-city set differs: schedule.json has an extra match in Dallas and one in San Francisco Bay Area that file #7 does not (file #7 instead has an extra match each in Philadelphia and Guadalajara).

**Round of 16** (8 matches each):
- Date spread differs: schedule.json is 2/2/2/2 across 2026-07-04..07; file #7 is 1/2/2/3.
- Venue-city set differs: schedule.json includes Philadelphia, Mexico City, Vancouver (1 each) that file #7 doesn't have at this stage; file #7 instead has Los Angeles (×2) and Miami that schedule.json doesn't have at this stage.

**Quarter-finals** (4 matches each):
- Date spread differs: schedule.json is 1/1/2 (07-09/10/11); file #7 is 1/2/1.
- Venue-city set differs: schedule.json has Boston, Miami, Kansas City; file #7 has Dallas, New York New Jersey, Houston instead (only Los Angeles agrees).

**Semi-finals** (2 matches, dates agree: 2026-07-14 and 2026-07-15):
- **Venue mismatch on the second semi-final** (2026-07-15): `schedule.json` says **Atlanta**; file #7 says **East Rutherford (New York/New Jersey metro)**. The first semi-final (2026-07-14) agrees on venue (Dallas / Arlington-normalized).

**Third-place match** (2026-07-18): agrees exactly — Miami, both sources.

**Final** (2026-07-19): agrees exactly — New York New Jersey / East Rutherford (same metro, both sources), teams are TBD placeholders in file #7 as expected.

### Summary of every discrepancy found
1. Group C, matchday 2 (2026-06-19): schedule.json pairs BRA-HAI & SCO-MAR; file #7 pairs BRA-SCO & MAR-HAI. **Genuine matchup conflict.**
2. 7 other group-stage matches (Groups B, D, F×2, J×2) play on a different date in file #7 vs schedule.json (1-day shifts, teams/pairing otherwise agree).
3. Round of 32: date-count distribution differs (schedule.json ends 07-03; file #7 extends to 07-04) and venue-city set differs by 2 cities each way.
4. Round of 16: date-count distribution differs and venue-city set differs by 2-3 cities each way.
5. Quarter-finals: date-count distribution differs and venue-city set differs by 3 cities each way (only LA agrees).
6. Semi-final #2 (2026-07-15): venue conflict — Atlanta (schedule.json) vs East Rutherford/NY-NJ (file #7).
7. FIFA ranking snapshot conflict (not a schedule/group item, but related): file #5 `fifa_ranking_pre_tournament` vs file #7 `team1_fifa_rank`/`team2_fifa_rank` disagree for 34/48 teams — likely two different ranking-list dates.

No discrepancies were found in: the 48-team group-letter assignments (zero mismatches), the total match count (104=104), the per-stage match counts (all equal), the group-stage team pairings themselves (all 72 matchups agree, only 8 have date conflicts as listed), the third-place match, or the final.

Per instructions, `schedule.json`, `groups.json`, and `venues.json` were **not modified** — this section is a report only, for a later wave to adjudicate against an authoritative source if reconciliation is desired.

---

## Notable decisions / constraints applied

- **No fabrication**: historical (2002-2022) xG left null; missing file #1 matches not backfilled; missing file #4 stats (10 matches) not backfilled; 2026 `venue`/`city` left null in `matches_historical.csv` because neither file #2 nor file #3 (the two sources used for the 2026 portion of the merge per task instructions) carry venue/city fields, and a trial join against file #7 by (date, team-pair) only resolved unambiguously for 46/88 real matches given the date/pairing discrepancies documented in section (d) above — populating the rest would have meant asserting unverified venue data as fact, which risks contaminating the training corpus.
- `database/schema.sql`, `database/seed.sql`, and the trusted `fifa_2026/*.json` files were **not** touched.
- The old broad "all competitions 1872-2017" dataset was **not** used as a source anywhere in this build.

---

## Output files produced

- `D:\Projects\fifa score predictor\backend\app\data\processed\matches_historical.csv` — 419 rows (330 historical 2002-2022 + 89 2026 real matches).
- `D:\Projects\fifa score predictor\backend\app\data\processed\teams_reference.csv` — 48 rows.
- `D:\Projects\fifa score predictor\backend\app\data\processed\match_team_stats.csv` — 132 rows.
- `D:\Projects\fifa score predictor\backend\app\data\processed\DATA_QUALITY_REPORT.md` — this file.
