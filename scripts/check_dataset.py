#!/usr/bin/env python3
"""Schema and integrity check for The War Atlas open dataset. Standard library only.

    python3 scripts/check_dataset.py            # check the files in the repo root, exit 1 on any failure
    python3 scripts/check_dataset.py --stats    # check, then print coverage stats as JSON
    python3 scripts/check_dataset.py DATA_DIR   # check another copy (e.g. a fresh download)

What it checks (every check is named, so a failure says exactly what broke):
  - every file in manifest.json exists, and its row count matches the manifest
  - row-count floors, so a truncated or half-written export fails instead of passing quietly
  - exact column headers per file (the schema in the README)
  - required fields are non-empty; numbers parse; enums hold allowed values
  - coordinates: lat and lng both present or both empty, inside [-90, 90] / [-180, 180], never (0, 0)
  - unique slugs per entity file, unique battle Wikidata QIDs, one estimate per (battle, side)
  - foreign keys: battle -> war, force/casualty -> battle and -> source, commander -> faction,
    battles.json commanders -> commanders.csv, battles.json source_slugs -> sources.csv
  - ranges: 0 <= low <= high
  - battles.json agrees with battles.csv, battle_forces.csv and battle_casualties.csv
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Minimum row counts for this snapshot (2026-07-03). A newer export may grow; it may not shrink
# without someone lowering a floor on purpose in a reviewed commit.
FLOORS = {
    "battles.csv": 3010,
    "battle_forces.csv": 3905,
    "battle_casualties.csv": 2713,
    "wars.csv": 493,
    "commanders.csv": 8012,
    "factions.csv": 425,
    "sources.csv": 19020,
    "battles.json": 3010,
}

SCHEMA = {
    "battles.csv": ["slug", "title", "war_slug", "campaign_slug", "year", "date_iso", "date_display",
                    "location", "lat", "lng", "coord_precision", "coord_source", "result", "intensity",
                    "confidence_level", "is_indexable", "wikidata_qid", "wikipedia_url", "url"],
    "battle_forces.csv": ["battle_slug", "side", "strength_low", "strength_high", "confidence", "source_slug"],
    "battle_casualties.csv": ["battle_slug", "side", "casualties_low", "casualties_high", "confidence", "source_slug"],
    "wars.csv": ["slug", "title", "era_slug", "period", "start_year", "end_year", "status", "wikidata_qid", "url"],
    "commanders.csv": ["slug", "name", "primary_faction_slug", "birth_year", "death_year", "wikidata_qid", "url"],
    "factions.csv": ["slug", "name", "wikidata_qid", "url"],
    "sources.csv": ["slug", "source_type", "title", "url"],
}

REQUIRED = {
    "battles.csv": ["slug", "title", "war_slug", "year", "date_display", "intensity", "is_indexable",
                    "wikidata_qid", "wikipedia_url", "url"],
    "battle_forces.csv": ["battle_slug", "strength_low", "strength_high", "confidence"],
    "battle_casualties.csv": ["battle_slug", "casualties_low", "casualties_high", "confidence"],
    "wars.csv": ["slug", "title", "era_slug", "period", "start_year", "end_year", "status", "wikidata_qid", "url"],
    "commanders.csv": ["slug", "name", "url"],
    "factions.csv": ["slug", "name", "url"],
    "sources.csv": ["slug", "source_type", "title"],
}

QID = re.compile(r"^Q[1-9][0-9]*$")
DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
CONFIDENCE = {"low", "medium", "high"}
SITE = "https://thewaratlas.co/"


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def is_int(s: str) -> bool:
    return bool(re.fullmatch(r"-?\d+", s))


def is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


class Report:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name: str, bad: list, detail: str = "") -> None:
        """bad = offending items; empty means the check passed."""
        ok = not bad
        msg = detail if ok else f"{len(bad)} bad, e.g. {bad[:3]}"
        self.results.append((name, ok, msg))

    @property
    def failed(self) -> list[str]:
        return [n for n, ok, _ in self.results if not ok]


def run_checks(data_dir: Path, floors: dict[str, int] | None = None) -> tuple[Report, dict]:
    """Run every check. Returns the report and the loaded tables (for --stats)."""
    floors = FLOORS if floors is None else floors
    r = Report()
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.exists():
        r.check("files.manifest_present", ["manifest.json"])
        return r, {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    missing = [f for f in list(files) + list(SCHEMA) if not (data_dir / f).exists()]
    r.check("files.present", sorted(set(missing)), f"{len(files)} files listed in manifest.json")
    if missing:
        return r, {}

    T: dict[str, list[dict]] = {}
    for f in SCHEMA:
        header, rows = read_csv(data_dir / f)
        T[f] = rows
        r.check(f"schema.header[{f}]", [] if header == SCHEMA[f] else [f"got {header}"])
    if r.failed:  # later checks index columns by name; a wrong header would crash them
        return r, {}
    J = json.loads((data_dir / "battles.json").read_text(encoding="utf-8"))
    T["battles.json"] = J

    # Row counts: manifest agreement and floors.
    for f, meta in files.items():
        n = len(T[f]) if f in T else None
        r.check(f"rows.match_manifest[{f}]", [] if n == meta.get("rows") else [f"manifest {meta.get('rows')}, file {n}"], f"{n} rows")
    for f, floor in floors.items():
        n = len(T.get(f, []))
        r.check(f"rows.floor[{f}]", [] if n >= floor else [f"{n} < floor {floor}"], f"{n} >= {floor}")

    # Required fields.
    for f, cols in REQUIRED.items():
        bad = [(row.get("slug") or row.get("battle_slug"), c) for row in T[f] for c in cols if not row[c].strip()]
        r.check(f"required[{f}]", bad)

    B, F, C = T["battles.csv"], T["battle_forces.csv"], T["battle_casualties.csv"]
    W, CM, FA, S = T["wars.csv"], T["commanders.csv"], T["factions.csv"], T["sources.csv"]

    # Types and enums.
    r.check("types.battles.year_int", [b["slug"] for b in B if not is_int(b["year"])])
    r.check("types.battles.intensity_0_100",
            [b["slug"] for b in B if not (is_int(b["intensity"]) and 0 <= int(b["intensity"]) <= 100)])
    r.check("types.battles.is_indexable_bool", [b["slug"] for b in B if b["is_indexable"] not in ("True", "False")])
    r.check("types.battles.date_iso_matches_year",
            [b["slug"] for b in B if b["date_iso"] and not (DATE.match(b["date_iso"]) and is_int(b["year"])
                                                           and int(DATE.match(b["date_iso"]).group(1)) == int(b["year"]))])
    r.check("types.battles.confidence_level_enum", [b["slug"] for b in B if b["confidence_level"] not in CONFIDENCE | {""}])
    for f, rows in (("wars.csv", W), ("battles.csv", B)):
        r.check(f"types.qid[{f}]", [x["slug"] for x in rows if not QID.match(x["wikidata_qid"])])
    for f, rows in (("commanders.csv", CM), ("factions.csv", FA)):
        r.check(f"types.qid[{f}]", [x["slug"] for x in rows if x["wikidata_qid"] and not QID.match(x["wikidata_qid"])])
    r.check("types.wars.years",
            [w["slug"] for w in W if not (is_int(w["start_year"]) and is_int(w["end_year"]) and int(w["start_year"]) <= int(w["end_year"]))])
    r.check("types.commanders.years", [c["slug"] for c in CM for k in ("birth_year", "death_year") if c[k] and not is_int(c[k])])
    for f in ("battles.csv", "wars.csv", "commanders.csv", "factions.csv"):
        r.check(f"types.url_on_site[{f}]", [x["slug"] for x in T[f] if not x["url"].startswith(SITE)])

    # Coordinates.
    r.check("coords.both_or_neither", [b["slug"] for b in B if bool(b["lat"].strip()) != bool(b["lng"].strip())])
    coord_rows = [b for b in B if b["lat"].strip() and b["lng"].strip()]
    r.check("coords.numeric", [b["slug"] for b in coord_rows if not (is_float(b["lat"]) and is_float(b["lng"]))])
    numeric = [b for b in coord_rows if is_float(b["lat"]) and is_float(b["lng"])]
    r.check("coords.in_range", [b["slug"] for b in numeric if not (-90 <= float(b["lat"]) <= 90 and -180 <= float(b["lng"]) <= 180)])
    r.check("coords.not_null_island", [b["slug"] for b in numeric if float(b["lat"]) == 0 and float(b["lng"]) == 0])
    r.check("coords.precision_iff_coords",
            [b["slug"] for b in B if bool(b["lat"].strip()) != bool(b["coord_precision"]) or bool(b["lat"].strip()) != bool(b["coord_source"])])
    r.check("coords.precision_enum", [b["slug"] for b in B if b["coord_precision"] not in ("exact", "place", "")])

    # Uniqueness.
    for f in ("battles.csv", "wars.csv", "commanders.csv", "factions.csv", "sources.csv"):
        dup = [s for s, n in Counter(x["slug"] for x in T[f]).items() if n > 1]
        r.check(f"unique.slug[{f}]", dup)
    r.check("unique.battle_qid", [q for q, n in Counter(b["wikidata_qid"] for b in B).items() if n > 1])
    for f, rows in (("battle_forces.csv", F), ("battle_casualties.csv", C)):
        r.check(f"unique.battle_side[{f}]", [k for k, n in Counter((x["battle_slug"], x["side"]) for x in rows).items() if n > 1])

    # Foreign keys.
    bs, ws, ss = {b["slug"] for b in B}, {w["slug"] for w in W}, {s["slug"] for s in S}
    cs, fs = {c["slug"] for c in CM}, {f["slug"] for f in FA}
    r.check("fk.battle_war", [b["slug"] for b in B if b["war_slug"] not in ws])
    for f, rows in (("battle_forces.csv", F), ("battle_casualties.csv", C)):
        r.check(f"fk.battle[{f}]", [x["battle_slug"] for x in rows if x["battle_slug"] not in bs])
        r.check(f"fk.source[{f}]", [x["source_slug"] for x in rows if x["source_slug"] and x["source_slug"] not in ss])
    r.check("fk.commander_faction", [c["slug"] for c in CM if c["primary_faction_slug"] and c["primary_faction_slug"] not in fs])
    r.check("fk.json_commander", [c["slug"] for b in J for c in b.get("commanders", []) if c["slug"] not in cs])
    r.check("fk.json_source", [s for b in J for s in b.get("source_slugs", []) if s not in ss])

    # Ranges.
    for f, rows, k in (("battle_forces.csv", F, "strength"), ("battle_casualties.csv", C, "casualties")):
        r.check(f"range.int[{f}]", [x["battle_slug"] for x in rows if not (is_int(x[k + "_low"]) and is_int(x[k + "_high"]))])
        ints = [x for x in rows if is_int(x[k + "_low"]) and is_int(x[k + "_high"])]
        r.check(f"range.low_le_high[{f}]", [x["battle_slug"] for x in ints if not 0 <= int(x[k + "_low"]) <= int(x[k + "_high"])])
        r.check(f"range.confidence_enum[{f}]", [x["battle_slug"] for x in rows if x["confidence"] not in CONFIDENCE])

    # battles.json mirrors the CSVs.
    jb = {b["slug"]: b for b in J}
    r.check("json.unique_slug", [s for s, n in Counter(b["slug"] for b in J).items() if n > 1])
    r.check("json.same_battles_as_csv", sorted(bs ^ set(jb))[:10])
    scalar_bad = []
    for b in B:
        j = jb.get(b["slug"])
        if j is None:
            continue
        for k, cv in b.items():
            jv = j.get(k)
            jv = "" if jv is None else str(jv)
            if jv != cv and not (cv and is_float(cv) and is_float(jv) and float(cv) == float(jv)):
                scalar_bad.append((b["slug"], k))
    r.check("json.scalars_match_csv", scalar_bad)
    for f, rows, key in (("battle_forces.csv", F, "forces"), ("battle_casualties.csv", C, "casualties")):
        csv_set = Counter((x["battle_slug"], x["side"], x[f"{'strength' if key == 'forces' else 'casualties'}_low"],
                           x[f"{'strength' if key == 'forces' else 'casualties'}_high"], x["source_slug"]) for x in rows)
        lo = "strength_low" if key == "forces" else "casualties_low"
        hi = "strength_high" if key == "forces" else "casualties_high"
        json_set = Counter((b["slug"], e["side"], str(e[lo]), str(e[hi]), e.get("source_slug") or "") for b in J for e in b.get(key, []))
        r.check(f"json.{key}_match_csv", list(((csv_set - json_set) + (json_set - csv_set)).elements())[:10])
    return r, T


def pct(n: int, d: int) -> float:
    return round(100 * n / d, 1) if d else 0.0


def stats(T: dict) -> dict:
    """Coverage numbers for the README and the graphics. Computed, never typed."""
    B, F, C, J = T["battles.csv"], T["battle_forces.csv"], T["battle_casualties.csv"], T["battles.json"]
    W, CM, FA, S = T["wars.csv"], T["commanders.csv"], T["factions.csv"], T["sources.csv"]
    nb = len(B)
    coverage = {f: {c: pct(sum(1 for x in T[f] if x[c].strip()), len(T[f])) for c in SCHEMA[f]} for f in SCHEMA}
    with_coords = [b for b in B if b["lat"]]
    fb, cb = {x["battle_slug"] for x in F}, {x["battle_slug"] for x in C}
    years = [int(b["year"]) for b in B]
    decades = Counter((y // 25) * 25 for y in years)
    grid = Counter((int((float(b["lat"]) + 90) // 3), int((float(b["lng"]) + 180) // 3)) for b in with_coords)
    wiki = Counter(b["wikipedia_url"] for b in B)
    shared_wiki = {u: n for u, n in wiki.items() if n > 1}
    return {
        "rows": {f: len(T[f]) for f in FLOORS},
        "battles": {
            "total": nb,
            "with_coords": len(with_coords),
            "coord_precision": dict(Counter(b["coord_precision"] or "none" for b in B)),
            "year_min": min(years), "year_max": max(years),
            "date_iso_jan_1": sum(1 for b in B if b["date_iso"].endswith("-01-01")),
            "date_iso_empty": sum(1 for b in B if not b["date_iso"]),
            "with_forces": len(fb), "with_casualties": len(cb), "with_either": len(fb | cb),
            "with_commanders": sum(1 for b in J if b.get("commanders")),
            "with_source_refs": sum(1 for b in J if b.get("source_slugs")),
            "source_refs_total": sum(len(b.get("source_slugs", [])) for b in J),
            "commander_links_total": sum(len(b.get("commanders", [])) for b in J),
            "with_result": sum(1 for b in B if b["result"]),
            "is_indexable_false": sum(1 for b in B if b["is_indexable"] == "False"),
            "intensity_zero": sum(1 for b in B if b["intensity"] == "0"),
            "wikipedia_url_shared": {"urls": len(shared_wiki), "battles": sum(shared_wiki.values())},
            "wikipedia_url_equals_title": sum(1 for b in B if b["wikipedia_url"] == "https://en.wikipedia.org/wiki/" + b["title"].replace(" ", "_")),
            "same_title_and_year_pairs": sum(1 for n in Counter((b["title"], b["year"]) for b in B).values() if n > 1),
            "per_25_years": {str(k): v for k, v in sorted(decades.items())},
        },
        "estimates": {
            f: {
                "rows": len(rows),
                "with_source_slug": sum(1 for x in rows if x["source_slug"]),
                "point_values": sum(1 for x in rows if x[k + "_low"] == x[k + "_high"]),
                "confidence": dict(Counter(x["confidence"] for x in rows)),
                "max_high": max(int(x[k + "_high"]) for x in rows),
            } for f, rows, k in (("battle_forces.csv", F, "strength"), ("battle_casualties.csv", C, "casualties"))
        },
        "wars": {
            "total": len(W),
            "with_battles": len({b["war_slug"] for b in B}),
            "status": dict(Counter(w["status"] for w in W)),
            "era": dict(Counter(w["era_slug"] for w in W).most_common()),
        },
        "commanders": {"total": len(CM), "linked_from_battles": len({c["slug"] for b in J for c in b.get("commanders", [])})},
        "factions": {"total": len(FA), "shared_qids": sum(1 for n in Counter(f["wikidata_qid"] for f in FA if f["wikidata_qid"]).values() if n > 1)},
        "sources": {"total": len(S), "linked_from_battles": len({s for b in J for s in b.get("source_slugs", [])}),
                    "type": dict(Counter(s["source_type"] for s in S).most_common())},
        "coverage_pct": coverage,
        "map_grid_3deg": [[la * 3 - 90, lo * 3 - 180, n] for (la, lo), n in sorted(grid.items())],
    }


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    data_dir = Path(args[0]) if args else ROOT
    report, tables = run_checks(data_dir)
    want_stats = "--stats" in argv
    out = sys.stderr if want_stats else sys.stdout
    for name, ok, msg in report.results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {msg}".rstrip(), file=out)
    n, bad = len(report.results), report.failed
    print(f"\n{n - len(bad)}/{n} checks passed", file=out)
    if bad:
        print("FAILED: " + ", ".join(bad), file=out)
        return 1
    if want_stats:
        print(json.dumps(stats(tables), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
