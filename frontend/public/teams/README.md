# Player photographs

Local, same-origin player portraits. **Nothing in the running site may ever
request an image from a third party** — that is the whole reason this directory
exists.

## Convention

```
frontend/public/teams/<team-slug>/<player-slug>.webp
```

- `<team-slug>` — the registry team name, slugged. `Brazil` → `brazil`,
  `South Korea` → `south-korea`, `Côte d'Ivoire` → `cote-d-ivoire`,
  `Türkiye` → `turkiye`, `USA` → `usa`.
- `<player-slug>` — the player's name exactly as it appears in
  `backend/app/data/players.csv`, slugged. `Vinícius Júnior` →
  `vinicius-junior`, `Bruno Guimarães` → `bruno-guimaraes`.

The slug rule is one function, `slugify` in `src/lib/player-images.ts`: fold
diacritics, lowercase, collapse every run of non-alphanumerics to a single
hyphen, trim hyphens from the ends.

Example:

```
public/teams/
├── brazil/
│   ├── alisson.webp
│   ├── bruno-guimaraes.webp
│   ├── marquinhos.webp
│   └── vinicius-junior.webp
├── argentina/
├── france/
└── spain/
```

`.webp` is the documented default. `.png`, `.jpg`, `.jpeg` and `.avif` are also
indexed, but the resolver builds its URL as `.webp`, so anything else needs the
resolver's extension updated too — convert to `.webp` instead.

## The easy way: drop and ingest

You do not have to crop, convert or rename anything by hand.

```bash
npm run worklist:player-images        # who still needs a photograph
# ...save images into frontend/_incoming/<team-slug>/, any filename
npm run ingest:player-images          # crop 3:4, WebP, correct filename
npm run build:player-images           # regenerate the manifest
npm run audit:player-images           # verify all 48 teams
```

`_incoming/` is gitignored — the originals stay on your machine, only the
optimised WebP is committed.

Ingest resolves the filename to a squad member rather than trusting it:
`Vinícius Júnior.jpg`, `vinicius_junior.JPG` and `Vinicius-Junior (1).png` all
land on `brazil/vinicius-junior.webp`. It **refuses** a file that matches
nobody in that team's 26, and it refuses one that matches two people — dropping
`Santos.jpg` into `brazil/` fails with "ambiguous — could be Danilo Santos,
Douglas Santos" instead of picking one. A photograph filed against the wrong
man is worse than no photograph, so the tie is never broken by guessing.

Use `--dry-run` to preview and `--force` to replace an existing image.

## After adding or removing an image by hand

```bash
npm run build:player-images   # regenerate the manifest
npm run audit:player-images   # verify all 48 teams
```

The first rewrites `src/lib/player-images.generated.ts`, which is the list the
UI consults. **A file dropped here does nothing until the manifest is
regenerated** — that is deliberate. A missing photograph is the normal case, and
an optimistic `<img>` would fire one 404 per player (384 of them across the 48
team pages) and flash a broken-image glyph before the fallback swapped in.
Manifest-driven resolution means a player without a photograph renders the
monogram directly and issues no request at all.

## Format guidance

- Portrait crop, **3:4** — that is the aspect ratio the card, the captain hero
  and the dialog all frame. A square or landscape source will be centre-cropped
  from the top (`object-cover object-top`), which keeps the head but throws away
  the sides.
- ~600 × 800 is plenty; the largest render is the captain hero at ~224 px wide,
  so 2× covers every display.
- Keep files under ~60 KB. These are lazy-loaded except the captain's, but eight
  of them land on every team page.

## Licensing

Only add images you have the right to redistribute. FIFA's official squad
photographs are **not** in that category: they are not offered under a licence
that permits redistribution, and FIFA publishes no consumable squad-image API.
Do not scrape them, and do not hot-link them — hot-linking would reintroduce the
external request this whole design exists to avoid.

The monogram fallback is a supported, designed state, not a placeholder waiting
to be filled. Shipping with zero photographs is a correct outcome.
