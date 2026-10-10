#!/usr/bin/env node
/**
 * Turns a pile of loose photographs into correctly-named, correctly-shaped
 * local assets.
 *
 *   frontend/_incoming/<team-slug>/<anything>.{jpg,png,webp,avif,jpeg}
 *        ↓  npm run ingest:player-images
 *   frontend/public/teams/<team-slug>/<player-slug>.webp   600×800, WebP q82
 *
 * The filename you drop in does not have to be the slug — "Vinícius Júnior.jpg",
 * "vinicius_junior.JPG" and "Vinicius-Junior (1).png" all resolve to the same
 * player. What the file *cannot* do is resolve to somebody who is not in that
 * team's 26-man squad, or to two players at once: both are refused rather than
 * guessed, because a photograph filed against the wrong man is worse than no
 * photograph at all.
 *
 * This script never reaches the network. It reads local files, and the squad it
 * validates against is the committed dataset.
 *
 *   --dry-run      report what would happen, write nothing
 *   --force        overwrite an existing photograph
 *   --keep         leave the source file in _incoming (default: leave it alone
 *                  anyway — nothing is ever deleted from _incoming)
 */

import { readFileSync, readdirSync, statSync, existsSync, mkdirSync } from "node:fs";
import { join, dirname, extname, basename } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = join(HERE, "..");
const REPO = join(FRONTEND, "..");
const INCOMING = join(FRONTEND, "_incoming");
const TEAMS_DIR = join(FRONTEND, "public", "teams");
const PLAYERS_CSV = join(REPO, "backend", "app", "data", "players.csv");

const WIDTH = 600;
const HEIGHT = 800;          // 3:4, matching the aspect-[3/4] frames in the UI
const QUALITY = 82;
const SOURCE_EXT = new Set([".jpg", ".jpeg", ".png", ".webp", ".avif", ".tif", ".tiff"]);

const TEAM_ALIASES = {
  "Bosnia–Herz": "Bosnia and Herzegovina",
  "Korea Republic": "South Korea",
  "United States": "USA",
};
const NON_COMPOSING = { ø: "o", đ: "d", ð: "d", þ: "th", ł: "l", ß: "ss", æ: "ae", œ: "oe" };

function slugify(value) {
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

function loadSquads() {
  const byTeamSlug = new Map();
  for (const r of parseCsv(readFileSync(PLAYERS_CSV, "utf8"))) {
    const raw = (r.team ?? "").trim();
    const name = (r.player ?? "").trim();
    if (!raw || !name) continue;
    const team = TEAM_ALIASES[raw] ?? raw;
    const ts = slugify(team);
    if (!byTeamSlug.has(ts)) byTeamSlug.set(ts, { team, players: [] });
    byTeamSlug.get(ts).players.push({ name, slug: slugify(name) });
  }
  return byTeamSlug;
}

/**
 * Resolve a dropped filename to exactly one squad member.
 *
 * Exact slug first. Failing that, a surname match — but only when the surname
 * picks out a single player in that squad. Two Silvas means we stop and ask
 * rather than choose.
 */
function resolvePlayer(fileStem, squad) {
  const want = slugify(fileStem).replace(/-\d+$/, ""); // drop a trailing "(1)" copy suffix
  if (!want) return { error: "filename slugs to nothing" };

  const exact = squad.players.filter((p) => p.slug === want);
  if (exact.length === 1) return { player: exact[0], how: "exact" };
  if (exact.length > 1) return { error: `matches ${exact.length} squad members exactly` };

  const parts = want.split("-").filter(Boolean);
  const surname = parts[parts.length - 1];
  const candidates = squad.players.filter((p) => {
    const ps = p.slug.split("-");
    return ps.includes(surname) || p.slug.startsWith(want) || want.startsWith(p.slug);
  });
  if (candidates.length === 1) return { player: candidates[0], how: "surname" };
  if (candidates.length > 1) {
    return { error: `ambiguous — could be ${candidates.map((c) => c.name).join(", ")}` };
  }
  return { error: `no player in ${squad.team}'s squad matches "${fileStem}"` };
}

// ─── run ─────────────────────────────────────────────────────────────────────

const argv = process.argv.slice(2);
const dryRun = argv.includes("--dry-run");
const force = argv.includes("--force");

let sharp;
try {
  ({ default: sharp } = await import("sharp"));
} catch {
  console.error(
    "\ningest-player-images needs `sharp`.\n" +
    "  npm install\n" +
    "(sharp is a devDependency — it is used only by this script and never ships to the browser.)\n"
  );
  process.exit(1);
}

if (!existsSync(INCOMING)) {
  console.log(
    `\nNothing to ingest — ${INCOMING} does not exist.\n\n` +
    "Create it and drop photographs in per-team folders:\n" +
    "  frontend/_incoming/brazil/vinicius junior.jpg\n" +
    "  frontend/_incoming/brazil/Alisson.png\n\n" +
    "Run `npm run worklist:player-images` for the list of players to collect.\n"
  );
  process.exit(0);
}

const squads = loadSquads();
const done = [], skipped = [], failed = [];

for (const teamEntry of readdirSync(INCOMING).sort()) {
  const teamPath = join(INCOMING, teamEntry);
  if (!statSync(teamPath).isDirectory()) continue;

  const teamSlug = slugify(teamEntry);
  const squad = squads.get(teamSlug);
  if (!squad) {
    failed.push(`${teamEntry}/ — no WC2026 team slugs to "${teamSlug}"`);
    continue;
  }

  for (const file of readdirSync(teamPath).sort()) {
    const ext = extname(file).toLowerCase();
    if (!SOURCE_EXT.has(ext)) continue;

    const src = join(teamPath, file);
    const { player, how, error } = resolvePlayer(basename(file, extname(file)), squad);
    if (error) { failed.push(`${teamEntry}/${file} — ${error}`); continue; }

    const outDir = join(TEAMS_DIR, teamSlug);
    const out = join(outDir, `${player.slug}.webp`);
    if (existsSync(out) && !force) {
      skipped.push(`${teamSlug}/${player.slug}.webp already exists (use --force to replace)`);
      continue;
    }

    if (dryRun) {
      done.push({ team: squad.team, name: player.name, how, out: `${teamSlug}/${player.slug}.webp`, bytes: 0, from: file });
      continue;
    }

    mkdirSync(outDir, { recursive: true });
    try {
      const info = await sharp(src)
        .rotate()                                   // honour EXIF orientation
        .resize(WIDTH, HEIGHT, { fit: "cover", position: "top" })
        .webp({ quality: QUALITY, effort: 5 })
        .toFile(out);
      done.push({ team: squad.team, name: player.name, how, out: `${teamSlug}/${player.slug}.webp`, bytes: info.size, from: file });
    } catch (e) {
      failed.push(`${teamEntry}/${file} — could not process: ${e.message}`);
    }
  }
}

// ─── report ──────────────────────────────────────────────────────────────────

console.log(`\nIngest player images${dryRun ? "  (dry run — nothing written)" : ""}\n`);
for (const d of done) {
  const size = d.bytes ? `${(d.bytes / 1024).toFixed(0)} KB` : "—";
  console.log(`  ok    ${d.out.padEnd(44)} ${String(size).padStart(7)}  ${d.name}${d.how === "surname" ? "  (matched on surname)" : ""}`);
}
for (const s of skipped) console.log(`  skip  ${s}`);
for (const f of failed) console.error(`  FAIL  ${f}`);

console.log(
  `\n  ${done.length} processed, ${skipped.length} skipped, ${failed.length} failed\n`
);
if (done.length > 0 && !dryRun) {
  console.log("  Next:\n    npm run build:player-images\n    npm run audit:player-images\n");
}
process.exit(failed.length === 0 ? 0 : 1);
