import type { Team } from "@/types";

export type SortKey = "name" | "group" | "rank" | "elo";
export type SortDir = "asc" | "desc";

const collator = new Intl.Collator("en", { sensitivity: "base" });

/** First click on a column: A–Z, best FIFA rank first (lowest number), highest Elo first. */
export function defaultSortDir(key: SortKey): SortDir {
  return key === "elo" ? "desc" : "asc";
}

/** Plain-words description of the active sort, for the status line. */
export function describeSort(key: SortKey, dir: SortDir): string {
  switch (key) {
    case "name":
      return dir === "asc" ? "team name, A to Z" : "team name, Z to A";
    case "group":
      return dir === "asc" ? "group, A to L" : "group, L to A";
    case "rank":
      return dir === "asc" ? "FIFA rank, best first" : "FIFA rank, worst first";
    case "elo":
      return dir === "desc" ? "Elo rating, highest first" : "Elo rating, lowest first";
  }
}

type Sortable = Pick<Team, "name" | "wc2026_group" | "fifa_ranking" | "elo_rating">;

/**
 * Compares two teams. Rank and Elo are compared as numbers (never as text, where "10" < "9"). A team with no
 * value for the sorted column goes last in either direction, and ties fall back to the team name.
 */
export function compareTeams(a: Sortable, b: Sortable, key: SortKey, dir: SortDir): number {
  const sign = dir === "asc" ? 1 : -1;
  const byName = collator.compare(a.name, b.name);
  if (key === "name") return sign * byName;
  if (key === "group") {
    const d = collator.compare(a.wc2026_group ?? "~", b.wc2026_group ?? "~");
    return d !== 0 ? sign * d : byName;
  }
  const av = key === "rank" ? a.fifa_ranking : a.elo_rating;
  const bv = key === "rank" ? b.fifa_ranking : b.elo_rating;
  if (av == null && bv == null) return byName;
  if (av == null) return 1;
  if (bv == null) return -1;
  return av !== bv ? sign * (av - bv) : byName;
}
