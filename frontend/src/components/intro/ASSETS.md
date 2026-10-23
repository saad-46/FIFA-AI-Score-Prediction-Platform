# Intro assets

## External assets

Ten files are used, and only when the realistic footballers are requested
(`?introCharacter=realistic`):

- `public/intro/players.glb` (4,001,580 bytes = 4.00 MB, Meshopt-compressed
  with `--level medium` from 9.05 MB; 3,682,000 bytes with seven players and
  3,342,152 with six): all eight players. Every mesh is player 1, with players
  2 to 8 stored as morph targets (index order below); their skeletons are
  included unskinned so joint positions can be blended. Decoded with three's
  bundled Meshopt decoder.
- `public/intro/player-2-skin.webp` … `player-8-skin.webp` (34,618 / 36,992 /
  50,880 / 55,496 / 55,240 / 35,242 / 52,986 bytes): the later players' skin
  textures. `player-8-skin.webp` is Kane's, `player-7-skin.webp` Salah's;
  players 1 to 7 are byte-identical to the seven-player build (PNG sources
  compared with `cmp`; meshes and morph targets with `scripts/glbcmp.mjs`).
- `runs.json` and `shot.json`: the motion-capture data described below.

The asset order (the order of the morph targets, of `PLAYERS` in
`profiles.ts`, and of the skin files) is: 1 Messi, 2 Neymar, 3 Mbappe, 4
Haaland, 5 Modric, 6 Ronaldo, 7 Salah, 8 Kane. The cinematic order is
different: Salah and Kane were added last so the existing targets kept their
indices, and the timeline plays Messi, Neymar, Mbappe, Haaland, Kane, Salah,
Modric, Ronaldo (see Stage K below).

They were generated, not downloaded as finished models. A Blender script built
them from the sources below; the kits (shirt, shorts, socks) were grown from
the body surface by that script and are original.

| Source | Used for | Author / origin | Licence | Attribution required | Checked |
| --- | --- | --- | --- | --- | --- |
| MakeHuman base mesh, shape targets and `game_engine` rig, as bundled with MPFB 2.0.18 (https://extensions.blender.org/add-ons/mpfb/) | Body, face, hands, skeleton, skin weights | MakeHuman Community | Assets CC0 (the add-on's code is GPL-3.0-or-later; it is a build tool and is not shipped) | No | 2026-10-11 |
| MakeHuman system assets pack (https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip) | Skin textures `young_caucasian_male` (players 1 and 6), `young_african_male` (2), `middleage_african_male` (3), `young_caucasian_male2` (4), `middleage_caucasian_male` (5), the mean of `young_caucasian_male` and `young_african_male` (7, made by the build script from the two CC0 textures), the mean of `young_caucasian_male` and `middleage_caucasian_male` (8, likewise), eyes `low-poly`, `eyebrow001`, `eyelashes01`, hair `short02` (1), `afro01` (2), `short04` (3), `ponytail01` (4), `short03` (5), `short01` (6), `afro01` again for player 7 and `short04` again for player 8 (second instances, so each can be tinted separately), boots `shoes02` | MakeHuman Community | CC0 | No | 2026-10-11 |
| Blender 4.5.14 LTS (https://download.blender.org/release/Blender4.5/) | Build tool only | Blender Foundation | GPL; not shipped | No | 2026-10-11 |
| glTF-Transform CLI 4.2.1 (`npx @gltf-transform/cli`) | Build tool only: Meshopt compression | Don McCurdy | MIT; not shipped | No | 2026-10-17 |

Each face is a combination of generic MakeHuman shape sliders. None is
modelled on, or claimed to resemble, any real person; the footballers' names
appear only as captions.

The build tools and downloaded packs live outside this repository
(`D:/Tools/fifa-intro-assets`); the six-player script is `scripts/build_players.py` and the seven-player one `scripts/build_players7.py`, and the eight-player one `scripts/build_players8.py` there (steps in `scripts/README-players8.txt`; `README-players7.txt` is kept).

## Motion capture

Two runtime files, both used only in realistic mode:

- `public/intro/runs.json` (123 KB; about 35 KB transferred
  gzip-compressed): four running strides, each retargeted onto the intro's
  17-bone pose system and baked to quaternions, with the body's within-stride
  forward lead, hip height and the source runner's foot-contact flags. Used
  only for running.
- `public/intro/shot.json` (93 KB; about 22 KB transferred gzip-compressed):
  player 6's final strike, one non-looping clip (see The shot below).

`?introMotion=handbuilt` switches both off for comparison and
`?introMotion=handshot` keeps the runs and hand-builds only the shot. If a file
is missing or fails validation, that part stays hand-built. Touches, the pass
and the celebration stay hand-built: none of these clips contains ball work
other than the strike. Player 5's control touch and pass are procedural keyed poses (see Stage H below).

| Segment | Clip (CMU subject_trial, description) | Frames used (120 fps) |
| --- | --- | --- |
| Player 1 running in | `141_01` "Run" | 12-52 (one stride) |
| Player 3 burst and sprint | `143_01` "Run" | 2-44 |
| Player 4 driving run | `102_05` "RunningStraight" | 4-77 (one stride, trough to trough), rotated to start at frame 41 |
| Players 5-6 running onto the pass | `35_17` "run/jog" | 17-107 |

Source files: `141.asf`, `143.asf`, `102.asf`, `35.asf` and the `.amc` files
above, from http://mocap.cs.cmu.edu/subjects/<n>/.

| | |
| --- | --- |
| Source | CMU Graphics Lab Motion Capture Database, http://mocap.cs.cmu.edu. The terms are stated once for the whole database; there are no per-clip licences. |
| Licence, database home page (checked 2026-10-17) | "This dataset of motions is free for all uses." / "You may include this data in commercially-sold products, but you may not resell this data directly, even in converted form." |
| Licence, FAQ (checked 2026-10-17) | "The motion capture data may be copied, modified, or redistributed without permission." |
| Commercial use | Allowed |
| Modification, retargeting, baking | Allowed ("modified") |
| Redistribution | Allowed, but the data may not be resold, even converted. This project does not sell it; the baked strides ship inside a free website. |
| Attribution | Not required for use. Requested for published research: "The data used in this project was obtained from mocap.cs.cmu.edu. The database was created with funding from NSF EIA-0196217." Reproduced here as a courtesy. |
| Performers | Subjects are identified only by number; the data is joint motion only, with no face, voice or likeness. Subject 102 is listed as "Basketball"; subjects 141 and 143 as "General Subject Capture"; 35 as "walk, run". |

The licence terms above were read again on the live sites during the Stage G4
review (2026-10-17): the CMU home page and FAQ wording is unchanged, the
MakeHuman system assets are still listed as CC0, and MPFB is still listed as
GPL-3.0-or-later (code only; it is a build tool and is not shipped). Not
re-read in that review: the GSAP licence page (it did not return text), and the
npm packages' licences.

Only the derived strides and the derived strike are shipped. The source
ASF/AMC files, the reader (`scripts/mocap_fk.py`), the retarget-and-bake
scripts (`scripts/mocap_bake.py`, `scripts/mocap_bake_shot.py`) and the clip
analysis scripts (`scripts/mocap_stats.py`, `scripts/kick_compare.py`,
`scripts/kick_compare2.py`) live outside this repository in
`D:/Tools/fifa-intro-assets`.

### The shot

| | |
| --- | --- |
| Clip | CMU `10_06` ("soccer - kick ball", subject 10), http://mocap.cs.cmu.edu/subjects/10/10_06.amc with `10.asf`. Licence and attribution: as recorded above for the database (checked 2026-10-17). |
| Frames used | 337 to 553 at 120 fps: 0.6 s before ball contact to 1.2 s after. Contact is the frame of peak right-foot speed (frame 409; 12.7 m/s, with the toe 11 cm above the lowest marker, which is the ball's equator height). |
| Used for | Nothing in the default or realistic sequence any more: the final polish replaced the finish with a hand-built bicycle kick (see The finish below), and `m.shotWeight` is 0. The clip, `shot.json` and the `?introMotion=handshot` plumbing stay in place and are untested against the new finish. |
| Chosen over | `10_01`, `10_02` (standing starts), `10_03`, `10_05` and `11_01`, by approach, support-foot plant, follow-through and fit to the scene's run-up; see the report for the comparison. |
| Retargeting | `mocap_bake_shot.py`: the same positions-based method as the runs, with the figure frame set to the direction of the kicking foot at contact, so the runtime only has to turn the figure to the direction the ball leaves. The legs are retargeted against the shooter's own measured rest-pose leg vectors (the model's legs are splayed about 10 degrees, which the runs tolerate and a kick does not). Verified: the baked rotations reproduce the source leg directions to 0.0 degrees. |
| Runtime contact | The clip has no ball, so the ball's place is measured, not captured. On load the shooter's boot mesh is skinned at the contact frame and the figure is placed so a ball lying on the grass just touches it (no overlap before contact, measured separation 0 mm at contact and growing after). The ball is at rest until contact, then leaves at 1.25 times the boot's measured speed along the strike, reaching the net at the same time as before (`SHOT.launch` in `timeline.ts`). Only the clip's source and licence are external; none of this adds an asset. |

## Football motion research (Stage G)

It records what was searched and what was found, so the decision is not
repeated. Only `10_06` is used (the shot).

| Source | What it has | Licence | Verdict |
| --- | --- | --- | --- |
| CMU Graphics Lab Motion Capture Database, http://mocap.cs.cmu.edu, subject 10 ("kick soccer ball"): trials `10_01`, `10_02`, `10_03`, `10_05`, `10_06`; subject 11: trial `11_01`. (`10_04` is a walk.) | Right-footed soccer kicks with a short approach. Measured from the source data (foot speed, 120 fps): peak 10.9, 12.3, 12.7, 11.4, 12.7 and 13.5 m/s; approach speed 1.6 to 2.6 m/s. | The same CMU terms recorded under Motion capture above (checked 2026-10-17): free for all uses, may be modified and redistributed, may not be resold even converted. | Usable for a shot (`10_06` is used, see above). Not a pass: every trial is a full-power strike. |
| CMU subjects 6 and 15 | Basketball dribbling and passing | Same | Wrong ball and wrong action; not football. |
| KIT Whole-Body Human Motion Database, entry 1063 | A re-host of CMU `10_04` (a walk, despite the "kick" label) | The entry states no licence of its own | Not used. |
| Bandai Namco Research motion dataset | General motions | CC BY-NC-ND (no commercial use, no derivatives) | Excluded by the licence. |
| Total Capture (Surrey) | General motions | CC BY-NC | Excluded by the licence. |
| OpenBiomechanics (Driveline) | Baseball | CC BY-NC-SA | Excluded by the licence and wrong sport. |
| OmniContact (Hugging Face) | Includes soccer-ball kicking | Gated; no licence visible without accepting access terms | Not verified; not used. |

Not found under a verified licence: a grounded pass, dribbling or close
control with a football, a stepover, a flick. The CMU database has none of
them.

## Football motion research (Stage H, 2026-10-18)

Re-searched for a licensed pass or close-control capture. None was found, so
the pass and the control touch are procedural (no new file, no new licence).

| Candidate | Finding | Verdict |
| --- | --- | --- |
| CMU subjects 10 and 11 | Full-power kicks only (as above) | Shot only |
| Soccer-X (arXiv 2411.16216) | Dribble, trick and shoot capture; no release or licence found | Not used |
| OmniContact (Hugging Face) | Soccer kicking and carrying; gated, licence not visible | Not used |
| UPenn mocap library | The page did not load (404); not verified | Not used |

The CMU FAQ could not be re-fetched on 2026-10-18 (TLS certificate check
failed); the terms recorded above (read 2026-10-17) are unchanged as far as
verified. The full note is kept outside the repository with the stage's
evidence.

What is hand-built, in realistic mode only (p > 0.47): player 5's control
touch (`TOUCH` in `timeline.ts`) and pass (`PASS`), keyed in
`character/pose.ts` (monotone cubic keys per channel, contact at the middle of
the pass window); the ball stays put until `PASS.contact` and then rolls out
with a constant deceleration to where the shooter meets it. The procedural
default stops at p = 0.35 and is unaffected.

## Shirt numbers and the ending (Stage I)

Both are code, with no new files in `public/intro`.

- **Shirt numbers** (realistic figures only): `kit.number` in `profiles.ts` is
  the roster (Messi 10, Neymar 10, Mbappe 10, Haaland 9, Modric 10, Ronaldo 7, Salah 11, Kane 9;
  the file records how each was chosen and where the choice is uncertain). The
  digits come from one small canvas atlas drawn with the page's display face
  (Barlow Condensed, SIL OFL, already loaded by the site); the kit shader draws
  them on the shirt from each vertex's rest-pose position, so the number is on
  the cloth: large between the shoulder blades, small on the centre chest.
  They are visible face-on and from behind; in the side-on framing of most
  shots they are edge-on. The default procedural figure has no numbers.
- **The ending** (`ENDING` in `timeline.ts`): the SIIIUUU word (a bitmap, see Stage J), the fade to
  black and the closing message are DOM layers driven by progress; the shake is
  a decaying function of progress, so scrolling back reproduces it exactly.
  The closing message ("No live-action footage. No shortcuts. Just code.") is
  literally true of the footage (there is none) but not of the whole project:
  the figures and motion use the open-licensed assets recorded above, which is
  why the card carries a small note saying so.

## Salah, the roster order and the timeline (Stage J)

**Roster** (cinematic order; shirt number in brackets; asset index after it):
Messi (10, 0), Neymar (10, 1), Mbappe (10, 2), Haaland (9, 3), **Salah (11,
6)**, Modric (10, 4), Ronaldo (7, 5). Numbers are the national-team numbers the
other kits echo; Salah's 11 is his Liverpool number because his kit is a
Liverpool-style red (he wears 10 for Egypt). Ronaldo is last, immediately before
the ending.

**Salah's character** is original, like the others: MakeHuman slider values
(`PLAYERS[6]` in `scripts/build_players7.py`), no likeness is claimed. Build:
`blender -b --python build_players7.py -- <abs dir>` (about two minutes), then
`gltf-transform meshopt ... --level medium` (the level that reproduces the
shipped six-player file byte for byte), then sharp to WebP quality 85 (which
reproduces `player-2-skin.webp` byte for byte). `scripts/glbcmp.mjs` confirmed
that the base mesh and all five existing morph targets of the 14 meshes are
bit-identical in the seven-player file.

**Timeline.** Salah shares Haaland's driving run (the captured `drive` stride,
calibrated on his skeleton): Haaland becomes Salah on the second heavy touch
(morph 0.548 to 0.566) and Salah becomes Modric through the existing turn
(0.59 to 0.64). His stride length is Haaland's on purpose, so the run phase, and
with it the pass and the plant, are unchanged: the scene state for p < 0.866 is
identical to the six-player build apart from the camera and the morph cues.
There are now two progress scales: the scene scale p that every window in
`timeline.ts` is written on, and scroll progress P = fromScene(p). The drive
(p 0.52 to 0.59) is stretched 2.5x in P, so the scroll is 10.5% longer
(P_MAX = 1.105, about 74 more viewport heights) and each of the players has
75 to 190 viewport heights of scroll (Salah 75, Haaland 82, Modric 84).

**The finish (final polish).** Modric's pass is now a lob: the ball leaves his
boot at `PASS.contact` (p = 0.695), rises about 3.3 m and drops onto Ronaldo at
`SHOT.impact` (p = 0.804) at a constant 3.7 m/s horizontally. Ronaldo runs onto
it, plants, turns his back to the goal and plays a hand-built bicycle kick
(`BIKE_CLIP` in `character/pose.ts`: hips pitch back to about 1.6 rad, left leg
thrown up first, right leg whipped through the ball, arms out for balance;
the pelvis height is keyed and overrides the boot-based grounding while the kick
is on). Contact is at clip time 0.5, and the debug `bootGap` is 0.007 m at that
frame. The ball is driven only after contact: it leaves at about 22 m/s,
reaches about 40 m/s over the 25 ms boot-contact ramp and enters the net at
`FINISH.netHit` (p = 0.84). In the air it spins at a steady 12 rad/s (lob) and
50 rad/s (shot); on the grass it still rolls by distance. The net is a pure
function of the time since the hit (`goal.netT`): a damped spring pushes the cloth out
and back past rest, the dent widens as it travels, a ring crosses the panel
and the netting is drawn in toward the dent. The camera frames Ronaldo through
the kick, follows the ball into the goal, whips back to Ronaldo by p = 0.86, and
he gets up, runs about 2.7 m and jumps for SIII (`FINISH.jump`, `ENDING` and
the closing messages are unchanged). Scroll length is unchanged (P_MAX 1.18,
826 viewport heights plus the 80 hold): the new choreography re-keys the same
windows (p 0.695 to 0.908). Scene state for p < 0.69 and the ending constants
are checked against the earlier source (`roster-unit.mjs`, `ending-unit.mjs`).
Limits: the body is posed by a 17-bone Euler rig, so hands have no wrist
joint (only relaxed finger curl); the landing is a keyed roll, not a
physical simulation; the camera cannot show Ronaldo's landing and the ball in the
goal in the same frame (it follows the ball).

**Number beats.** Each player except Ronaldo gets one short swing of the camera
round him (with a 30% move-in) that shows the shirt number: `NUMBER_BEATS` in
`timeline.ts`. Ronaldo's jump already shows his back and then his front.

**Renderer fixes found while verifying determinism.** The face fill light was
placed from the camera position *before* the camera was updated, so the same
progress lit the face slightly differently depending on which way the viewer
had come (a one-frame lag; fixed in `world.ts`). The SIIIUUU word is now a
bitmap (an `<img>` from one 2D canvas drawn once per size) because live DOM
text in that layer was rasterised differently from visit to visit by the
browser's compositor, which also happens on a plain page with no application
code.

**Known limits.** Haaland's front number is small at its beat (light shirt, far
camera); players 1 to 5 are otherwise filmed side-on, so numbers are readable
only at the beats. The GPU-process stalls recorded in Stage H.4 are unresolved.

## Kane, the eight-player order and the timeline (Stage K)

**Roster** (cinematic order; shirt number; asset index): Messi (10, 0), Neymar
(10, 1), Mbappe (10, 2), Haaland (9, 3), **Kane (9, 7)**, Salah (11, 6), Modric
(10, 4), Ronaldo (7, 5). Kane's 9 is his England number on an England-style
kit (white shirt, navy shorts, white socks, navy digits; no crest or official
detail). Ronaldo is last, immediately before the ending, which is unchanged.

**Kane's character** is original, like the others: MakeHuman slider values
(`PLAYERS[7]` in `scripts/build_players8.py`: tall, broad, a squarer face and a
prominent nose), skin = the mean of the CC0 textures `young_caucasian_male` and
`middleage_caucasian_male` (mixed on a copy, because Blender shares the first
as one datablock with players 1 and 6), the CC0 hair `short04` as a second
instance tinted light brown. No likeness is claimed. Build:
`blender -b --python build_players8.py -- <absolute dir>` (about two minutes),
`gltf-transform meshopt ... --level medium`, then sharp to WebP quality 85.
Verified: the 15 meshes' base positions and all 90 morph targets of players 1
to 7 are identical to the seven-player build (worst absolute difference 0),
and skin PNGs 2 to 7 are byte-identical.

**Timeline.** Haaland, Kane and Salah share the captured `drive` stride
(calibrated on each skeleton) and the start of the turn; each has Haaland's
stride length, so the run phase, the pass and the plant are unchanged: the
scene state is identical to the six-player source for the whole scene scale
p < 0.866 apart from camera, dust and seam blur. Haaland becomes Kane on the
first heavy touch (morph 0.543 to 0.557), Kane becomes Salah on the second
(0.576 to 0.590), and Salah becomes Modric through the existing turn (0.59 to
0.64). Scroll progress P stretches the scene scale 0.52 to 0.62 by 2.8, so
P_MAX = 1.18 (826 viewport heights in all; six players were 700, seven 773).
Scroll per player (viewport heights): Messi 171, Neymar 91, Mbappe 84, Haaland
76, Kane 65, Salah 63, Modric 90, Ronaldo 185.

**Number beats.** One camera swing per player except Ronaldo (`NUMBER_BEATS`):
Messi back, Neymar front, Mbappe back, Haaland front (with a 45 % move-in; his
nine was small), Kane back, Salah front, Modric front. Ronaldo's jump shows his
back and then his front.

**Preserved from Stage J:** the face fill light is placed after the camera is
set (world.ts); the SIIIUUU word is a bitmap `<img>`, not live text or a second
`<canvas>`; the number and word fonts resolve through the `font-display`
class (Barlow Condensed).

**Known limits.** Kane and Salah share Haaland's run (a gait, not a new
animation). Players 1 to 5 are filmed side-on outside their beats. The
GPU-process stalls recorded in Stage H.4 are unresolved. Measured in Stage K on
a loaded machine, they are listed in the Stage K report.

## Procedural content

Everything else on screen, including the default (procedural) player, is
generated in code when the intro mounts:

| Thing | How it is made | File |
| --- | --- | --- |
| Player body | Lofted rings skinned to a 17-bone skeleton, one morph target per profile | `character/body-geometry.ts` |
| Kit, skin | Shader: colours, stripes and checkers computed per pixel | `character/kit-material.ts` |
| Hair, beard, face | three.js primitives | `character/hair.ts`, `character/rig.ts` |
| Animation | Computed per frame from progress; no clips | `character/pose.ts` |
| Football | Sphere with a shader panel pattern | `ball.ts` |
| Pitch, stand, floodlights | Shader markings, a canvas-drawn speck texture, additive quads | `stadium.ts` |

The player figures are original stylised characters. The footballers' names
appear only as captions ("Inspired by the playing style of ..."); no face,
likeness, federation or club crest, sponsor mark or official kit is reproduced.

## Libraries

Code dependencies, installed from npm. None is a paid product.

| Package | Licence |
| --- | --- |
| `three` | MIT |
| `@react-three/fiber` | MIT |
| `gsap` (with ScrollTrigger) | GSAP Standard "no charge" licence, https://gsap.com/standard-license (not MIT) |

If an external asset is ever added, record it here first: name, source URL,
author, licence, and the date the licence was checked.
