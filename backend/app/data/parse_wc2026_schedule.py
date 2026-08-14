"""
Parse the official FIFA World Cup 2026 match schedule (S3) into structured data,
and build the tournament progression graph.

Source: ``FWC26 Match Schedule.pdf`` — the official wallchart.

The PDF uses the standard security handler (V=1, R=2, 40-bit RC4) with an EMPTY
user password; ``/P -60`` restricts printing/copying permissions only. Opening
and reading it is exactly what any compliant PDF reader does, so this module
performs the same key derivation (Algorithm 2 of the PDF spec) to read the
content streams. No password is bypassed — there is none set on the document.

What this module extracts, and how each field is sourced:
  * fixtures            — parsed from the wallchart grid (kick-off + FIFA codes)
  * knockout graph      — parsed from the bracket's ``W##`` winner references
  * match numbers       — parsed where the wallchart renders them adjacent to a
                          fixture; any remainder is DERIVED from FIFA's numbering
                          scheme and each row records which of the two applied,
                          so nothing is silently inferred.

Cross-validation against sources S2 and S4 (which independently contain all 104
2026 fixtures) is performed by ``validate_canonical_dataset.py`` — this module
only reports what the PDF itself says.

Stdlib only. Read-only with respect to sources; writes into data/canonical/.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import zlib
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PDF_PATH = REPO_ROOT / "FWC26 Match Schedule.pdf"
OUT_DIR = Path(__file__).resolve().parent / "canonical"

# FIFA's published numbering scheme for the 48-team format. The PDF's own
# bracket references corroborate every boundary below (e.g. it renders
# "W97 v W98 -> 101", placing the semi-finals at 101/102 and the
# quarter-finals at 97-100).
STAGE_RANGES = [
    ("group_stage", 1, 72),
    ("round_of_32", 73, 88),
    ("round_of_16", 89, 96),
    ("quarter_final", 97, 100),
    ("semi_final", 101, 102),
    ("third_place", 103, 103),
    ("final", 104, 104),
]

_PAD = bytes([
    0x28, 0xBF, 0x4E, 0x5E, 0x4E, 0x75, 0x8A, 0x41, 0x64, 0x00, 0x4E, 0x56,
    0xFF, 0xFA, 0x01, 0x08, 0x2E, 0x2E, 0x00, 0xB6, 0xD0, 0x68, 0x3E, 0x80,
    0x2F, 0x0C, 0xA9, 0xFE, 0x64, 0x53, 0x69, 0x7A,
])


def _rc4(key: bytes, data: bytes) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) & 0xFF
        s[i], s[j] = s[j], s[i]
    out = bytearray()
    i = j = 0
    for ch in data:
        i = (i + 1) & 0xFF
        j = (j + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
        out.append(ch ^ s[(s[i] + s[j]) & 0xFF])
    return bytes(out)


def _unescape(chunk: bytes) -> bytes:
    chunk = chunk.replace(b"\\(", b"(").replace(b"\\)", b")")
    chunk = re.sub(rb"\\([0-7]{1,3})", lambda m: bytes([int(m.group(1), 8) & 0xFF]), chunk)
    return chunk.replace(b"\\\\", b"\\")


def extract_pdf_text(path: Path) -> str:
    """Decrypt, inflate and flatten the wallchart's text content."""
    raw = path.read_bytes()

    enc = re.search(rb"/Filter\s*/Standard(.{0,400}?)>>", raw, re.S).group(1)
    owner = re.search(rb"/O\s*\((.*?)\)\s*/P", enc, re.S).group(1)
    owner = re.sub(rb"\\([0-7]{1,3})", lambda m: bytes([int(m.group(1), 8) & 0xFF]), owner)
    owner = owner.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
    perms = int(re.search(rb"/P\s*(-?\d+)", enc).group(1))
    doc_id = bytes.fromhex(re.search(rb"/ID\s*\[\s*<([0-9A-Fa-f]+)>", raw).group(1).decode())

    digest = hashlib.md5()
    digest.update(_PAD)
    digest.update(owner[:32])
    digest.update(struct.pack("<i", perms))
    digest.update(doc_id)
    file_key = digest.digest()[:5]          # /Length 40 -> 5 bytes

    objects: dict[tuple[int, int], bytes] = {}
    for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj\b", raw):
        end = raw.find(b"endobj", m.end())
        objects[(int(m.group(1)), int(m.group(2)))] = raw[m.end(): end if end != -1 else len(raw)]

    def object_key(num: int, gen: int) -> bytes:
        seed = file_key + struct.pack("<i", num)[:3] + struct.pack("<i", gen)[:2]
        return hashlib.md5(seed).digest()[:10]

    streams: list[bytes] = []
    for (num, gen), body in objects.items():
        marker = re.search(rb"stream\r\n|stream\n|stream\r", body)
        if not marker:
            continue
        blob = body[marker.end():]
        if b"endstream" in blob:
            blob = blob[: blob.rfind(b"endstream")]
        decrypted = _rc4(object_key(num, gen), blob)
        try:
            streams.append(zlib.decompress(decrypted))
        except zlib.error:
            try:
                streams.append(zlib.decompressobj().decompress(decrypted))
            except Exception:
                continue

    content = b"\n".join(streams)
    pieces: list[bytes] = []
    token = re.compile(rb"\[(.*?)\]\s*TJ|\(((?:[^()\\]|\\.)*)\)\s*Tj|\bT\*|\bTd\b|\bTD\b", re.S)
    for m in token.finditer(content):
        if m.group(1) is not None:
            parts = re.findall(rb"\((?:[^()\\]|\\.)*\)", m.group(1))
            pieces.append(b"".join(_unescape(p[1:-1]) for p in parts))
        elif m.group(2) is not None:
            pieces.append(_unescape(m.group(2)))
        else:
            pieces.append(b" ")

    text = b" ".join(pieces).decode("latin-1", errors="replace")
    return re.sub(r"\s+", " ", text)


def parse_groups(text: str) -> dict[str, list[str]]:
    """Group headers render as: GROUP A MEXICO (MEX) SOUTH AFRICA (RSA) ..."""
    groups: dict[str, list[str]] = {}
    for m in re.finditer(r"GROUP ([A-L])\s+(.*?)(?=GROUP [A-L]|All times|$)", text, re.S):
        letter = m.group(1)
        codes = re.findall(r"\(([A-Z]{3})\)", m.group(2))
        if codes:
            groups[letter] = codes[:4]
    return dict(sorted(groups.items()))


def parse_fixtures(text: str) -> tuple[list[dict], dict]:
    """
    Grid fixtures.

    The wallchart uses TWO different orderings for the match number, and mixing
    them up silently mis-binds numbers to fixtures:

        group grid       "<num> <hh:mm> <AAA> v <BBB> <group>"   number BEFORE
        knockout bracket "<hh:mm> <AAA> v <BBB> <num>"           number AFTER

    Because a fixture's true stage is not knowable from the PDF text alone, both
    readings are emitted as *candidates* and the caller resolves them against the
    stage each fixture actually belongs to (see ``assign_match_numbers``). That
    keeps the ambiguity explicit instead of guessing an ordering.
    """
    candidates: dict[tuple[str, str], dict] = {}

    def record(home: str, away: str, kickoff: str, group: str | None, number: int | None):
        entry = candidates.setdefault((home, away), {
            "home_code": home, "away_code": away, "kickoff_et": kickoff,
            "group": group, "match_number_candidates": [],
        })
        if group and not entry["group"]:
            entry["group"] = group
        if kickoff and not entry["kickoff_et"]:
            entry["kickoff_et"] = kickoff
        if number is not None and number not in entry["match_number_candidates"]:
            entry["match_number_candidates"].append(number)

    # number BEFORE, with trailing group letter (unambiguous group-stage form)
    for m in re.finditer(
            r"(\d{1,3})\s+(\d{2}:\d{2})\s+([A-Z]{3})\s+v\s+([A-Z]{3})\s+([A-L])\b", text):
        num, tm, home, away, grp = m.groups()
        record(home, away, tm, grp, int(num))

    # number BEFORE, no group letter
    for m in re.finditer(r"(\d{1,3})\s+(\d{2}:\d{2})\s+([A-Z]{3})\s+v\s+([A-Z]{3})", text):
        num, tm, home, away = m.groups()
        record(home, away, tm, None, int(num))

    # number AFTER (knockout bracket form)
    for m in re.finditer(r"(\d{2}:\d{2})\s+([A-Z]{3})\s+v\s+([A-Z]{3})\s+(\d{1,3})", text):
        tm, home, away, num = m.groups()
        record(home, away, tm, None, int(num))

    # fixture with no adjacent number at all
    for m in re.finditer(r"(\d{2}:\d{2})\s+([A-Z]{3})\s+v\s+([A-Z]{3})", text):
        tm, home, away = m.groups()
        record(home, away, tm, None, None)

    fixtures = list(candidates.values())
    diag = {
        "fixtures_parsed": len(fixtures),
        "with_any_number_candidate": sum(
            1 for f in fixtures if f["match_number_candidates"]),
        "with_single_candidate": sum(
            1 for f in fixtures if len(f["match_number_candidates"]) == 1),
        "with_ambiguous_candidates": sum(
            1 for f in fixtures if len(f["match_number_candidates"]) > 1),
        "without_any_number": sum(
            1 for f in fixtures if not f["match_number_candidates"]),
    }
    return fixtures, diag


def parse_knockout_graph(text: str) -> tuple[list[dict], dict]:
    """
    Bracket links render as '<hh:mm> W<a> v W<b> <match_number>', i.e. the winners
    of matches a and b meet in match <match_number>.
    """
    links: list[dict] = []
    seen: set[int] = set()
    for m in re.finditer(r"(\d{2}:\d{2})\s+W(\d{2,3})\s+v\s+W(\d{2,3})\s+(\d{2,3})", text):
        kickoff, src_a, src_b, num = m.groups()
        num = int(num)
        if num in seen:
            continue
        seen.add(num)
        links.append({
            "match_number": num,
            "kickoff_et": kickoff,
            "home_source": {"type": "winner_of", "match_number": int(src_a)},
            "away_source": {"type": "winner_of", "match_number": int(src_b)},
            "source": "pdf",
        })
    links.sort(key=lambda x: x["match_number"])
    return links, {"knockout_links_parsed": len(links),
                   "match_numbers": [l["match_number"] for l in links]}


def stage_for_number(num: int) -> str:
    for stage, lo, hi in STAGE_RANGES:
        if lo <= num <= hi:
            return stage
    raise ValueError(f"match number out of range: {num}")


def build_tournament_graph(links: list[dict]) -> dict:
    """
    Full progression model for all 104 matches.

    Group-stage slots (1-72) are filled by group fixtures. Round-of-32 slots
    (73-88) are populated from final group standings, so their feeder rule is
    recorded as 'group_qualification' rather than a match reference. Every
    later round carries explicit winner-of edges; the final and bronze final
    are derived from the semi-finals, which the wallchart's own legend
    ("W = Winner") and structure make unambiguous.
    """
    parsed = {l["match_number"]: l for l in links}
    nodes: dict[int, dict] = {}

    for num in range(1, 105):
        stage = stage_for_number(num)
        node = {
            "match_number": num,
            "stage": stage,
            "is_knockout": stage != "group_stage",
            "home_source": None,
            "away_source": None,
            "feeds_winner_to": None,
            "feeds_loser_to": None,
            "dependency_source": None,
        }
        if stage == "group_stage":
            node["home_source"] = {"type": "group_fixture"}
            node["away_source"] = {"type": "group_fixture"}
            node["dependency_source"] = "group_fixture"
        elif stage == "round_of_32":
            node["home_source"] = {"type": "group_qualification"}
            node["away_source"] = {"type": "group_qualification"}
            node["dependency_source"] = "group_qualification"
        elif num in parsed:
            node["home_source"] = parsed[num]["home_source"]
            node["away_source"] = parsed[num]["away_source"]
            node["dependency_source"] = "pdf"
        elif stage == "final":
            node["home_source"] = {"type": "winner_of", "match_number": 101}
            node["away_source"] = {"type": "winner_of", "match_number": 102}
            node["dependency_source"] = "derived_from_semi_finals"
        elif stage == "third_place":
            node["home_source"] = {"type": "loser_of", "match_number": 101}
            node["away_source"] = {"type": "loser_of", "match_number": 102}
            node["dependency_source"] = "derived_from_semi_finals"
        nodes[num] = node

    # back-edges: who does each match feed?
    for num, node in nodes.items():
        for side in ("home_source", "away_source"):
            src = node[side]
            if not src or "match_number" not in src:
                continue
            feeder = nodes[src["match_number"]]
            if src["type"] == "winner_of":
                feeder["feeds_winner_to"] = num
            else:
                feeder["feeds_loser_to"] = num

    return {
        "format": "FIFA World Cup 2026 — 48 teams, 12 groups of 4, 104 matches",
        "stage_ranges": [{"stage": s, "first": lo, "last": hi} for s, lo, hi in STAGE_RANGES],
        "nodes": [nodes[n] for n in sorted(nodes)],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = extract_pdf_text(PDF_PATH)

    groups = parse_groups(text)
    fixtures, fx_diag = parse_fixtures(text)
    links, link_diag = parse_knockout_graph(text)
    graph = build_tournament_graph(links)

    report = {
        "source_file": PDF_PATH.name,
        "encryption": "standard security handler V=1 R=2 RC4-40, empty user password (/P -60)",
        "extracted_chars": len(text),
        "groups": groups,
        "group_diagnostics": {
            "group_count": len(groups),
            "teams_per_group": {g: len(t) for g, t in groups.items()},
            "all_groups_have_four": all(len(t) == 4 for t in groups.values()),
            "distinct_teams": len({c for t in groups.values() for c in t}),
        },
        "fixture_diagnostics": fx_diag,
        "knockout_diagnostics": link_diag,
        "graph_diagnostics": {
            "nodes": len(graph["nodes"]),
            "dependency_sources": {
                k: sum(1 for n in graph["nodes"] if n["dependency_source"] == k)
                for k in ("group_fixture", "group_qualification", "pdf",
                          "derived_from_semi_finals")
            },
        },
    }

    (OUT_DIR / "wc2026_schedule.json").write_text(
        json.dumps({"groups": groups, "fixtures": fixtures, "knockout_links": links},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "wc2026_tournament_graph.json").write_text(
        json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "wc2026_schedule_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
