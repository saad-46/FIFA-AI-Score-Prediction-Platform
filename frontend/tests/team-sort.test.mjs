// Run with: npm test   (Node's built-in runner; TypeScript is loaded by Node's type stripping)
import test from "node:test";
import assert from "node:assert/strict";
import { compareTeams, defaultSortDir, describeSort } from "../src/lib/team-sort.ts";

const t = (name, rank, elo, group = "A") => ({ name, fifa_ranking: rank, elo_rating: elo, wc2026_group: group });
const teams = [t("Brazil", 6, 2030), t("Argentina", 1, 2150), t("Qatar", 55, 1600), t("Spain", 2, 2120), t("Haiti", 10, null), t("Ghana", null, 1700), t("Japan", 9, 1900)];
const order = (key, dir) => [...teams].sort((a, b) => compareTeams(a, b, key, dir)).map((x) => x.name);

test("FIFA rank sorts numerically, best (lowest number) first by default", () => {
  assert.equal(defaultSortDir("rank"), "asc");
  // "10" would sort before "2" as text; numerically 9 < 10 < 55
  assert.deepEqual(order("rank", "asc"), ["Argentina", "Spain", "Brazil", "Japan", "Haiti", "Qatar", "Ghana"]);
});
test("FIFA rank descending reverses the numbers but keeps missing values last", () => {
  assert.deepEqual(order("rank", "desc"), ["Qatar", "Haiti", "Japan", "Brazil", "Spain", "Argentina", "Ghana"]);
});
test("Elo sorts numerically, highest first by default", () => {
  assert.equal(defaultSortDir("elo"), "desc");
  assert.deepEqual(order("elo", "desc"), ["Argentina", "Spain", "Brazil", "Japan", "Ghana", "Qatar", "Haiti"]);
});
test("Elo ascending keeps missing values last", () => {
  assert.deepEqual(order("elo", "asc"), ["Qatar", "Ghana", "Japan", "Brazil", "Spain", "Argentina", "Haiti"]);
});
test("team name sorts A-Z and Z-A", () => {
  assert.deepEqual(order("name", "asc"), ["Argentina", "Brazil", "Ghana", "Haiti", "Japan", "Qatar", "Spain"]);
  assert.deepEqual(order("name", "desc"), ["Spain", "Qatar", "Japan", "Haiti", "Ghana", "Brazil", "Argentina"]);
});
test("equal values fall back to the team name", () => {
  const same = [t("Zed", 5, 1800), t("Abe", 5, 1800)];
  assert.deepEqual(same.sort((a, b) => compareTeams(a, b, "rank", "asc")).map((x) => x.name), ["Abe", "Zed"]);
});
test("the active sort is described in words", () => {
  assert.equal(describeSort("rank", "asc"), "FIFA rank, best first");
  assert.equal(describeSort("elo", "desc"), "Elo rating, highest first");
});
