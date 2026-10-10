#!/usr/bin/env node
/**
 * The photo shopping list: every player the team pages actually display,
 * with the exact filename each photograph must be saved as.
 *
 *   npm run worklist:player-images
 *   npm run worklist:player-images -- --api http://localhost:8000/api/v1
 *   npm run worklist:player-images -- --missing-only
 *
 * Writes `player-image-worklist.csv` and `player-image-worklist.md` next to
 * the repo root, and prints per-team coverage.
 *
 * Offline it reads the committed datasets; with `--api` it reads the served
 * key-player ranking, which is authoritative. The ranking is never
 * recomputed here — see the note in audit-player-images.mjs for why a second
 * copy of it would be worse than useless.
 */

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = join(HERE, "..");
const REPO = join(FRONTEND, "..");
const MANIFEST = join(FRONTEND, "src", "lib", "player-images.generated.ts");
const PLAYERS_CSV = join(REPO, "backend", "app", "data", "players.csv");
const MATCH_STATS_CSV = join(
  REPO, "backend", "app", "data", "canonical", "canonical_match_stats.csv"
);

const TEAM_ALIASES = {
  "Bosnia–Herz": "Bosnia and Herzegovina",
  "Korea Republic": "South Korea",
  "United States": "USA",
};

const NON_COMPOSING = { ø: "o", đ: "d", ð: "d", þ: "th", ł: "l", ß: "ss", æ: "ae", œ: "oe" };

export function slugify(value) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[øđðþłßæœ]/g, (c) => NON_COMPOSING[c] ?? c)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function parseCsv(text) {
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else quoted = false; }
      else field += c;
      continue;
    }
    if (c === '"') { quoted = true; continue; }
    if (c === ",") { row.push(field); field = ""; continue; }
    if (c === "\r") continue;
    if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; continue; }
    field += c;
  }
  if (field.length > 0 || row.length > 0) { row.push(field); rows.push(row); }
  const header = rows.shift() ?? [];
  return rows.filter((r) => r.length > 1)
    .map((r) => Object.fromEntries(header.map((h, i) => [h.trim(), (r[i] ?? "").trim()])));
}

function manifestKeys() {
  if (!existsSync(MANIFEST)) return new Set();
  const src = readFileSync(MANIFEST, "utf8");
  const body = src.slice(src.indexOf("new Set(["), src.indexOf("]);"));
  return new Set([...body.matchAll(/"([^"]+)"/g)].map((m) => m[1]));
}

async function fromApi(apiBase) {
  const teams = await fetch(`${apiBase}/teams/wc2026`).then((r) => r.json());
  const out = [];
  for (const t of teams) {
    const s = await fetch(`${apiBase}/teams/${t.id}/squad`).then((r) => r.json());
    for (const [i, p] of s.key_players.entries()) {
      out.push({
        team: s.team,
        rank: i + 1,
        name: p.name,
        isCaptain: s.captain?.name === p.name,
        position: p.position ?? "",
        club: p.club ?? "",
        games: p.games ?? "",
      });
    }
  }
  return out;
}

/** Offline: squad order stands in for the ranking, which lives on the server. */
function fromCsv() {
  const rows = parseCsv(readFileSync(PLAYERS_CSV, "utf8"));
  const byTeam = new Map();
  for (const r of rows) {
    const raw = (r.team ?? "").trim();
    if (!raw) continue;
    const team = TEAM_ALIASES[raw] ?? raw;
    if (!byTeam.has(team)) byTeam.set(team, []);
    byTeam.get(team).push({
      name: (r.player ?? "").trim(),
      position: (r.position ?? "").trim(),
      club: (r.club ?? "").trim(),
      games: Number(r.games || 0),
    });
  }

  const captains = new Map();
  if (existsSync(MATCH_STATS_CSV)) {
    for (const r of parseCsv(readFileSync(MATCH_STATS_CSV, "utf8"))) {
      const raw = (r.team ?? "").trim();
      const cap = (r.captain ?? "").trim();
      const date = (r.date ?? "").trim();
      if (!raw || !cap) continue;
      const team = TEAM_ALIASES[raw] ?? raw;
      const prev = captains.get(team);
      if (!prev || date > prev.date) captains.set(team, { date, captain: cap });
    }
  }

  const out = [];
  for (const team of [...byTeam.keys()].sort()) {
    const capName = captains.get(team)?.captain;
    const played = byTeam.get(team).filter((p) => p.games > 0);
    const ordered = [
      ...played.filter((p) => p.name === capName),
      ...played.filter((p) => p.name !== capName).sort((a, b) => b.games - a.games),
    ].slice(0, 8);
    for (const [i, p] of ordered.entries()) {
      out.push({ team, rank: i + 1, name: p.name, isCaptain: p.name === capName, position: p.position, club: p.club, games: p.games });
    }
  }
  return out;
}

const argv = process.argv.slice(2);
const apiFlag = argv.indexOf("--api");
const apiBase = apiFlag !== -1 ? argv[apiFlag + 1] : process.env.AUDIT_API_BASE ?? null;
const missingOnly = argv.includes("--missing-only");

const have = manifestKeys();
const players = apiBase ? await fromApi(apiBase) : fromCsv();

const rowsAll = players.map((p) => {
  const key = `${slugify(p.team)}/${slugify(p.name)}`;
  return { ...p, key, path: `frontend/public/teams/${key}.webp`, hasImage: have.has(key) };
});
const rows = missingOnly ? rowsAll.filter((r) => !r.hasImage) : rowsAll;

// ─── CSV ─────────────────────────────────────────────────────────────────────

const csvEsc = (v) => (/[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
writeFileSync(
  join(REPO, "player-image-worklist.csv"),
  ["team,rank,player,is_captain,position,club,appearances,target_file,has_image"]
    .concat(rows.map((r) =>
      [r.team, r.rank, r.name, r.isCaptain ? "yes" : "", r.position, r.club, r.games, r.path, r.hasImage ? "yes" : ""]
        .map(csvEsc).join(",")))
    .join("\n") + "\n",
  "utf8"
);

// ─── Markdown checklist ──────────────────────────────────────────────────────

const byTeam = new Map();
for (const r of rows) {
  if (!byTeam.has(r.team)) byTeam.set(r.team, []);
  byTeam.get(r.team).push(r);
}

const md = [
  "# Player photograph work list",
  "",
  apiBase
    ? "Generated by `npm run worklist:player-images --api …` from the **live squad API**, so this is the authoritative key-player ranking."
    : "> **Approximate.** Generated offline, where the eight players per team are\n" +
      "> ordered by appearances rather than by the server's importance score — the\n" +
      "> real ranking also weights starts, goals, assists, saves and clean sheets.\n" +
      "> Roughly 90% of rows differ from the authoritative list. Start the backend\n" +
      "> and re-run with `--api http://localhost:8000/api/v1` before collecting\n" +
      "> photographs, or you will source images for players the page never shows.",
  "",
  "Save each photograph into `frontend/_incoming/<team-slug>/` under **any** filename —",
  "`npm run ingest:player-images` matches it to the player, crops to 3:4, converts to",
  "WebP and writes it to the target path below. Or write the target file directly.",
  "",
  `**${rowsAll.filter((r) => r.hasImage).length} of ${rowsAll.length}** displayed players have a photograph.`,
  "",
];
for (const [team, list] of byTeam) {
  md.push(`## ${team}  \`${slugify(team)}\``, "");
  for (const r of list) {
    const tick = r.hasImage ? "x" : " ";
    const cap = r.isCaptain ? " **(captain)**" : "";
    md.push(`- [${tick}] \`${slugify(r.name)}.webp\` — ${r.name}${cap} · ${r.position || "?"} · ${r.club || "club unknown"}`);
  }
  md.push("");
}
writeFileSync(join(REPO, "player-image-worklist.md"), md.join("\n"), "utf8");

// ─── console ─────────────────────────────────────────────────────────────────

const teams = new Set(rowsAll.map((r) => r.team));
const withImg = rowsAll.filter((r) => r.hasImage).length;
const captains = rowsAll.filter((r) => r.isCaptain);
console.log(`\nPlayer photograph work list  (${apiBase ? "live API" : "offline datasets"})\n`);
console.log(`  ${String(teams.size).padStart(5)}  teams`);
console.log(`  ${String(rowsAll.length).padStart(5)}  displayed players`);
console.log(`  ${String(captains.length).padStart(5)}  captains`);
console.log(`  ${String(withImg).padStart(5)}  with a photograph`);
console.log(`  ${String(rowsAll.length - withImg).padStart(5)}  still on the monogram fallback`);
console.log(`\n  wrote player-image-worklist.csv and player-image-worklist.md`);
if (!apiBase) {
  console.log(
    "\n  WARNING: offline mode orders each team's eight by appearances, which is\n" +
    "  not the server's importance score — about 90% of rows differ from the\n" +
    "  authoritative list. Start the backend and re-run with:\n" +
    "    npm run worklist:player-images -- --api http://localhost:8000/api/v1"
  );
}
console.log("");
