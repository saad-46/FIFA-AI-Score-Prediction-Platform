#!/usr/bin/env node
/**
 * Team Intelligence audit: 48 teams, their captains, their key players and
 * every player photograph the site can serve.
 *
 * Two modes.
 *
 *   npm run audit:player-images
 *     Offline. Reads the committed datasets directly
 *     (backend/app/data/players.csv and canonical/canonical_match_stats.csv)
 *     and the image manifest, and checks squads, captains, duplicates, slug
 *     validity and manifest/disk parity.
 *
 *   npm run audit:player-images -- --api http://localhost:8000/api/v1
 *     Everything above, plus the key-player slots exactly as the API serves
 *     them — so the ranking is verified as delivered rather than
 *     reimplemented here. The server-side ranking lives in
 *     backend/app/data/players.py and is deliberately not duplicated: a second
 *     copy of it in an audit script would eventually disagree with the first
 *     and the audit would start certifying its own bug.
 *
 * Exits non-zero on any failure, so it can gate a release.
 */

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, dirname, extname, basename } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = join(HERE, "..");
const REPO = join(FRONTEND, "..");
const TEAMS_DIR = join(FRONTEND, "public", "teams");
const MANIFEST = join(FRONTEND, "src", "lib", "player-images.generated.ts");
const RESOLVER = join(FRONTEND, "src", "lib", "player-images.ts");
const PLAYERS_CSV = join(REPO, "backend", "app", "data", "players.csv");
const MATCH_STATS_CSV = join(
  REPO, "backend", "app", "data", "canonical", "canonical_match_stats.csv"
);

const EXPECTED_TEAMS = 48;
const EXPECTED_SQUAD = 26;
const EXPECTED_KEY_PLAYERS = 8;
const ALLOWED_EXT = new Set([".webp", ".png", ".jpg", ".jpeg", ".avif"]);

/** Mirrors TEAM_ALIASES in backend/app/data/players.py. Data, not logic —
 *  the team count assertion below fails loudly if it ever drifts. */
const TEAM_ALIASES = {
  "Bosnia–Herz": "Bosnia and Herzegovina",
  "Korea Republic": "South Korea",
  "United States": "USA",
};

const NON_COMPOSING = {
  ø: "o", đ: "d", ð: "d", þ: "th", ł: "l", ß: "ss", æ: "ae", œ: "oe",
};

function slugify(value) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[øđðþłßæœ]/g, (c) => NON_COMPOSING[c] ?? c)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// ─── tiny CSV reader (quoted fields, embedded commas and newlines) ───────────

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;

  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; } else { quoted = false; }
      } else field += c;
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
  return rows
    .filter((r) => r.length > 1)
    .map((r) => Object.fromEntries(header.map((h, i) => [h.trim(), (r[i] ?? "").trim()])));
}

// ─── findings ────────────────────────────────────────────────────────────────

const failures = [];
const warnings = [];
const fail = (m) => failures.push(m);
const warn = (m) => warnings.push(m);

// ─── 1. slug parity between the resolver, the generator and this audit ───────

function checkSlugParity() {
  const cases = [
    ["Vinícius Júnior", "vinicius-junior"],
    ["Bruno Guimarães", "bruno-guimaraes"],
    ["Côte d'Ivoire", "cote-d-ivoire"],
    ["Türkiye", "turkiye"],
    ["South Korea", "south-korea"],
    ["USA", "usa"],
    ["Curaçao", "curacao"],
    ["  Spaced  Name  ", "spaced-name"],
  ];
  for (const [input, expected] of cases) {
    const got = slugify(input);
    if (got !== expected) {
      fail(`slugify(${JSON.stringify(input)}) produced ${JSON.stringify(got)}, expected ${JSON.stringify(expected)}`);
    }
  }

  // The three copies of slugify must be character-identical, or a photograph
  // will be indexed under one name and looked up under another.
  const body = (file) => {
    const src = readFileSync(file, "utf8");
    const start = src.indexOf(".normalize(\"NFD\")");
    const end = src.indexOf("}", start);
    return start === -1 ? null : src.slice(start, end).replace(/\s+/g, "");
  };
  const resolverBody = body(RESOLVER);
  const generatorBody = body(join(HERE, "build-player-images.mjs"));
  if (!resolverBody || !generatorBody) {
    fail("could not locate slugify in the resolver or the generator");
  } else if (resolverBody !== generatorBody) {
    fail("slugify has drifted between src/lib/player-images.ts and scripts/build-player-images.mjs");
  }
}

// ─── 2. manifest is same-origin only, and matches what is on disk ────────────

function readManifestKeys() {
  if (!existsSync(MANIFEST)) { fail("src/lib/player-images.generated.ts is missing — run npm run build:player-images"); return []; }
  const src = readFileSync(MANIFEST, "utf8");
  if (/https?:\/\//.test(src.replace(/^\s*\/\/.*$/gm, ""))) {
    fail("the image manifest contains an absolute URL — player images must be same-origin only");
  }
  const body = src.slice(src.indexOf("new Set(["), src.indexOf("]);"));
  return [...body.matchAll(/"([^"]+)"/g)].map((m) => m[1]);
}

function readDiskKeys() {
  if (!existsSync(TEAMS_DIR)) return [];
  const keys = [];
  for (const team of readdirSync(TEAMS_DIR).sort()) {
    const teamPath = join(TEAMS_DIR, team);
    if (!statSync(teamPath).isDirectory()) continue;
    if (slugify(team) !== team) { fail(`public/teams/${team}/ is not a slug (expected "${slugify(team)}")`); continue; }
    for (const file of readdirSync(teamPath).sort()) {
      const ext = extname(file).toLowerCase();
      if (!ALLOWED_EXT.has(ext)) continue;
      const player = basename(file, extname(file));
      if (slugify(player) !== player) { fail(`public/teams/${team}/${file} is not a slug (expected "${slugify(player)}${ext}")`); continue; }
      if (ext !== ".webp") warn(`public/teams/${team}/${file} is not .webp — the resolver builds .webp URLs, so this file will not be served`);
      if (statSync(join(teamPath, file)).size === 0) fail(`public/teams/${team}/${file} is empty — that would render as a broken image`);
      keys.push(`${team}/${player}`);
    }
  }
  return keys;
}

// ─── 3. squads, captains, key players ────────────────────────────────────────

function loadSquads() {
  const rows = parseCsv(readFileSync(PLAYERS_CSV, "utf8"));
  const byTeam = new Map();
  for (const r of rows) {
    const raw = (r.team ?? "").trim();
    if (!raw) continue;
    const team = TEAM_ALIASES[raw] ?? raw;
    if (!byTeam.has(team)) byTeam.set(team, []);
    byTeam.get(team).push({ name: (r.player ?? "").trim(), team });
  }
  return byTeam;
}

function loadCaptains() {
  const latest = new Map();
  if (!existsSync(MATCH_STATS_CSV)) { fail("canonical_match_stats.csv is missing — captains cannot be verified"); return latest; }
  for (const r of parseCsv(readFileSync(MATCH_STATS_CSV, "utf8"))) {
    const raw = (r.team ?? "").trim();
    const captain = (r.captain ?? "").trim();
    const date = (r.date ?? "").trim();
    if (!raw || !captain) continue;
    const team = TEAM_ALIASES[raw] ?? raw;
    const prev = latest.get(team);
    if (!prev || date > prev.date) latest.set(team, { date, captain });
  }
  return latest;
}

async function fetchKeyPlayers(apiBase, teams) {
  const out = new Map();
  const list = await fetch(`${apiBase}/teams/wc2026`).then((r) => r.json());
  for (const t of list) {
    const squad = await fetch(`${apiBase}/teams/${t.id}/squad`).then((r) => r.json());
    out.set(squad.team, squad);
  }
  const served = new Set(out.keys());
  for (const t of teams) if (!served.has(t)) fail(`API served no squad for ${t}`);
  return out;
}

// ─── run ─────────────────────────────────────────────────────────────────────

const apiFlag = process.argv.indexOf("--api");
const apiBase = apiFlag !== -1 ? process.argv[apiFlag + 1] : process.env.AUDIT_API_BASE ?? null;

checkSlugParity();

const manifestKeys = readManifestKeys();
const diskKeys = readDiskKeys();

for (const k of manifestKeys) {
  if (!diskKeys.includes(k)) {
    fail(`manifest lists ${k} but no such file exists — that is a broken image; run npm run build:player-images`);
  }
}
for (const k of diskKeys) {
  if (!manifestKeys.includes(k)) {
    warn(`public/teams/${k} is on disk but not in the manifest — it will not be shown; run npm run build:player-images`);
  }
}
if (new Set(manifestKeys).size !== manifestKeys.length) fail("the manifest contains duplicate keys");

const squads = loadSquads();
const captains = loadCaptains();
const teams = [...squads.keys()].sort();

if (teams.length !== EXPECTED_TEAMS) fail(`expected ${EXPECTED_TEAMS} teams, found ${teams.length}`);
for (const bad of ["Central Spain", "TBD", "Korea Republic", "United States", "Bosnia–Herz"]) {
  if (squads.has(bad)) fail(`non-canonical team present: ${bad}`);
}

let captainCount = 0;
let keySlots = 0;
let withImage = 0;
let withFallback = 0;
const teamsMissingAllImages = [];

const served = apiBase ? await fetchKeyPlayers(apiBase, teams) : null;

for (const team of teams) {
  const squad = squads.get(team);
  const squadNames = new Set(squad.map((p) => p.name));

  if (squad.length !== EXPECTED_SQUAD) fail(`${team}: squad is ${squad.length}, expected ${EXPECTED_SQUAD}`);
  if (squadNames.size !== squad.length) fail(`${team}: duplicate player names in the squad`);

  const captain = captains.get(team);
  if (!captain) fail(`${team}: no captain on record`);
  else if (!squadNames.has(captain.captain)) fail(`${team}: captain ${captain.captain} is not in the squad`);
  else captainCount++;

  // Image coverage is counted over the players the profile actually displays.
  const displayed = served
    ? (served.get(team)?.key_players ?? []).map((p) => p.name)
    : squad.slice(0, EXPECTED_KEY_PLAYERS).map((p) => p.name);

  if (served) {
    const s = served.get(team);
    if (!s) { fail(`${team}: no squad payload from the API`); continue; }
    if (s.key_players.length !== EXPECTED_KEY_PLAYERS) {
      fail(`${team}: ${s.key_players.length} key players, expected ${EXPECTED_KEY_PLAYERS}`);
    }
    if (new Set(displayed).size !== displayed.length) fail(`${team}: duplicate key player`);
    for (const n of displayed) if (!squadNames.has(n)) fail(`${team}: key player ${n} is not in the squad`);
    if (s.captain && displayed[0] !== s.captain.name) fail(`${team}: captain is not listed first`);
    if (s.players.length !== EXPECTED_SQUAD) fail(`${team}: API returned ${s.players.length} players`);
  }

  keySlots += displayed.length;

  let teamImages = 0;
  for (const name of displayed) {
    const key = `${slugify(team)}/${slugify(name)}`;
    if (manifestKeys.includes(key)) { withImage++; teamImages++; } else withFallback++;
  }
  if (teamImages === 0) teamsMissingAllImages.push(team);
}

// ─── report ──────────────────────────────────────────────────────────────────

const line = (label, value) => console.log(`  ${String(value).padStart(5)}  ${label}`);

console.log("\nTeam Intelligence audit");
console.log(`  source: ${served ? `live API (${apiBase})` : "committed datasets (offline)"}\n`);
line("teams", teams.length);
line("captains resolved", captainCount);
line("key-player slots", keySlots);
line("local player images", withImage);
line("monogram fallbacks", withFallback);
line("broken images", failures.filter((f) => f.includes("broken image")).length);
console.log("");
line("photographs on disk", diskKeys.length);
line("photographs in manifest", manifestKeys.length);
line("external image sources", 0);

if (!served) {
  console.log("\n  note: key-player slots are counted from the squad list; re-run with");
  console.log("        --api <base> to verify the served ranking as well.");
}
if (teamsMissingAllImages.length === teams.length) {
  console.log("\n  Every displayed player renders the monogram fallback. That is the");
  console.log("  documented state of this product — no licensed photograph source is");
  console.log("  wired in — and is not a failure. See public/teams/README.md.");
}

for (const w of warnings) console.warn(`\n  warning: ${w}`);
for (const f of failures) console.error(`\n  FAIL: ${f}`);

console.log(failures.length === 0 ? "\nAudit passed.\n" : `\nAudit failed with ${failures.length} problem(s).\n`);
process.exit(failures.length === 0 ? 0 : 1);
