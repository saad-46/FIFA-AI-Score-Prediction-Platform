/**
 * Bundles the 48 WC2026 national flags into public/flags/ as local SVGs.
 *
 * Why a script rather than hand-drawn SVGs: several of these flags carry
 * detailed emblems (Brazil's celestial globe, Mexico's eagle, South Korea's
 * trigrams, Portugal's armillary sphere, Saudi Arabia's shahada). Redrawing
 * them by hand would produce subtly wrong national flags, which is worse than
 * showing none. Assets come from `flag-icons` (MIT), copied in at build time
 * and committed, so the app has no runtime dependency on the package and no
 * external/CDN request — see TeamFlag.tsx.
 *
 * Files are named by **FIFA code** (bra.svg, ksa.svg), matching the canonical
 * team identity the rest of the app keys on, so no component ever has to know
 * about ISO codes.
 *
 * Run: npm run build:flags
 */

import { copyFileSync, existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SOURCE = join(__dirname, "..", "node_modules", "flag-icons", "flags", "4x3");
const TARGET = join(__dirname, "..", "public", "flags");

/**
 * FIFA code -> ISO 3166-1 alpha-2, for the 48 WC2026 qualifiers only.
 *
 * FIFA codes are not ISO codes and the differences are exactly where a naive
 * mapping picks the wrong country: KSA is Saudi Arabia (sa), not Kosovo;
 * SUI is Switzerland (ch); GER is Germany (de); NED is the Netherlands (nl);
 * RSA is South Africa (za); CRO is Croatia (hr); POR is Portugal (pt);
 * DEN/SWE/SUI etc. all differ. Each entry below is stated explicitly rather
 * than derived, so a wrong flag cannot slip in silently.
 *
 * England and Scotland have no ISO country code; flag-icons ships them under
 * the GB subdivision codes gb-eng / gb-sct.
 */
const FIFA_TO_ISO = {
  ALG: "dz", // Algeria
  ARG: "ar", // Argentina
  AUS: "au", // Australia
  AUT: "at", // Austria
  BEL: "be", // Belgium
  BIH: "ba", // Bosnia and Herzegovina
  BRA: "br", // Brazil
  CPV: "cv", // Cabo Verde
  CAN: "ca", // Canada
  COL: "co", // Colombia
  COD: "cd", // Congo DR
  CRO: "hr", // Croatia
  CUW: "cw", // Curaçao
  CZE: "cz", // Czechia
  CIV: "ci", // Côte d'Ivoire
  ECU: "ec", // Ecuador
  EGY: "eg", // Egypt
  ENG: "gb-eng", // England
  FRA: "fr", // France
  GER: "de", // Germany
  GHA: "gh", // Ghana
  HAI: "ht", // Haiti
  IRN: "ir", // IR Iran
  IRQ: "iq", // Iraq
  JPN: "jp", // Japan
  JOR: "jo", // Jordan
  MEX: "mx", // Mexico
  MAR: "ma", // Morocco
  NED: "nl", // Netherlands
  NZL: "nz", // New Zealand
  NOR: "no", // Norway
  PAN: "pa", // Panama
  PAR: "py", // Paraguay
  POR: "pt", // Portugal
  QAT: "qa", // Qatar
  KSA: "sa", // Saudi Arabia
  SCO: "gb-sct", // Scotland
  SEN: "sn", // Senegal
  RSA: "za", // South Africa
  KOR: "kr", // South Korea
  ESP: "es", // Spain
  SWE: "se", // Sweden
  SUI: "ch", // Switzerland
  TUN: "tn", // Tunisia
  TUR: "tr", // Türkiye
  USA: "us", // USA
  URU: "uy", // Uruguay
  UZB: "uz", // Uzbekistan
};

if (!existsSync(SOURCE)) {
  console.error(
    `flag-icons assets not found at ${SOURCE}.\n` +
      `Run "npm install" first — flag-icons is a devDependency used only to produce public/flags.`
  );
  process.exit(1);
}

// Rebuild from scratch so a removed team cannot leave a stale flag behind.
if (existsSync(TARGET)) rmSync(TARGET, { recursive: true, force: true });
mkdirSync(TARGET, { recursive: true });

const missing = [];
for (const [fifa, iso] of Object.entries(FIFA_TO_ISO)) {
  const from = join(SOURCE, `${iso}.svg`);
  if (!existsSync(from)) {
    missing.push(`${fifa} -> ${iso}.svg`);
    continue;
  }
  copyFileSync(from, join(TARGET, `${fifa.toLowerCase()}.svg`));
}

if (missing.length) {
  console.error(`Missing source flags:\n  ${missing.join("\n  ")}`);
  process.exit(1);
}

const written = readdirSync(TARGET).filter((f) => f.endsWith(".svg"));
const expected = Object.keys(FIFA_TO_ISO).length;
if (written.length !== expected) {
  console.error(`Expected ${expected} flags, wrote ${written.length}`);
  process.exit(1);
}

console.log(`Bundled ${written.length} WC2026 flags into public/flags/`);
