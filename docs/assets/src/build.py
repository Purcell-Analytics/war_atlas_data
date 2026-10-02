"""Build the README graphics from committed captures. Every number comes from captures/*.json.

    python docs/assets/src/build.py
    uv run --with playwright==1.56.0 --with pillow python docs/assets/src/render.py docs/assets/src docs/assets
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
import check_dataset  # noqa: E402  (column names come from the checker's SCHEMA)
from readme_kit import box, arrows, esc, heading, hero, load_capture, page, write_pages  # noqa: E402

cap = load_capture(HERE / "captures" / "stats.json")
S = json.loads(cap["output"])
integrity = load_capture(HERE / "captures" / "integrity.json")["output"]
checks_line = [ln for ln in integrity.splitlines() if ln.endswith("checks passed")][0]  # e.g. "79/79 checks passed"
n_checks = checks_line.split("/")[0]
from datetime import datetime
from zoneinfo import ZoneInfo

DAY = datetime.fromisoformat(cap["captured_at"]).astimezone(ZoneInfo("America/Chicago")).date().isoformat()  # Central date
FOOT_REAL = f"WAR_ATLAS_DATA · REAL RUN {DAY}"

B, E, R = S["battles"], S["estimates"], S["rows"]
fz, cz = E["battle_forces.csv"], E["battle_casualties.csv"]


def n(x: int) -> str:
    return f"{x:,}"


def pct(a: int, b: int) -> float:
    return 100 * a / b


# ── 1. hero: map of every located battle + battles per 25 years ──────────────────────────────

def world_map(grid: list, w: int = 600, h: int = 300) -> str:
    peak = max(c for _, _, c in grid)
    dots = []
    for lat, lng, c in grid:
        x = (lng + 1.5 + 180) / 360 * w
        y = (90 - (lat + 1.5)) / 180 * h
        r = 1.6 + 6.5 * (c / peak) ** 0.5
        op = 0.45 + 0.55 * (c / peak) ** 0.5
        dots.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='{r:.1f}' fill='#E8912D' fill-opacity='{op:.2f}'/>")
    lines = "".join(f"<line x1='0' y1='{h * k / 6:.0f}' x2='{w}' y2='{h * k / 6:.0f}' stroke='#211f1c'/>" for k in range(1, 6))
    lines += "".join(f"<line x1='{w * k / 12:.0f}' y1='0' x2='{w * k / 12:.0f}' y2='{h}' stroke='#211f1c'/>" for k in range(1, 12))
    return (f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}' style='background:#121110;border:1px solid #2a2724;border-radius:10px'>"
            f"{lines}{''.join(dots)}</svg>")


def histogram(per: dict, w: int = 600, h: int = 150) -> str:
    items = list(per.items())
    peak = max(per.values())
    bw = w / len(items)
    bars = []
    for i, (start, c) in enumerate(items):
        bh = (h - 34) * c / peak
        x = i * bw + 5
        bars.append(f"<rect x='{x:.1f}' y='{h - 22 - bh:.1f}' width='{bw - 10:.1f}' height='{bh:.1f}' rx='3' fill='#C27F21'/>"
                    f"<text x='{x + (bw - 10) / 2:.1f}' y='{h - 26 - bh:.1f}' text-anchor='middle' font-family='JetBrains Mono' font-size='11' fill='#a39d93'>{c}</text>"
                    f"<text x='{x + (bw - 10) / 2:.1f}' y='{h - 6}' text-anchor='middle' font-family='JetBrains Mono' font-size='11' fill='#6d675f'>{start}</text>")
    return f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'>{''.join(bars)}</svg>"


right = (f"<div><div class='k' style='font-size:12px;margin-bottom:10px'>{n(B['with_coords'])} located battles, 3° cells</div>"
         f"{world_map(S['map_grid_3deg'])}"
         f"<div class='k' style='font-size:12px;margin:26px 0 6px'>battles per 25 years, {B['year_min']} to {B['year_max']}</div>"
         f"{histogram(B['per_25_years'])}</div>")

hero_html = hero(
    kicker="OPEN DATASET · CC BY 4.0 · THEWARATLAS.CO",
    title=f"{n(R['battles.csv'])} battles.",
    accent="Every count checked.",
    lede_html=(f"{n(R['wars.csv'])} wars, {n(R['commanders.csv'])} commanders, {n(R['sources.csv'])} source records, "
               "in plain CSV and nested JSON. A CI check fails the build if a row breaks the schema."),
    rules=[
        (f"{n(B['with_coords'])} battles on the map",
         f"{pct(B['with_coords'], B['total']):.1f}% have lat/lng: {n(B['coord_precision']['exact'])} exact, {n(B['coord_precision']['place'])} place-level"),
        (f"{n(fz['rows'] + cz['rows'])} force and casualty estimates",
         f"{n(fz['rows'])} force rows and {n(cz['rows'])} casualty rows, each stored as low and high"),
        (f"{n_checks} integrity checks in CI",
         "row floors, unique ids, valid coordinates, foreign keys, JSON equals CSV"),
    ],
    pill="LOAD IT IN PYTHON OR JS IN ONE CALL",
    right_html=right,
    footer_left=FOOT_REAL,
)

# ── 2. schema: files, row counts (capture), join keys (checker) ──────────────────────────────

def fields(f: str, k: int) -> list[str]:
    cols = check_dataset.SCHEMA[f]
    return [", ".join(cols[i:i + 3]) for i in range(0, min(len(cols), k), 3)]


bx = "".join([
    box(56, 200, 330, 150, f"wars.csv · {n(R['wars.csv'])}", fields("wars.csv", 9)),
    box(520, 190, 360, 190, f"battles.csv · {n(R['battles.csv'])}", fields("battles.csv", 15) + ["... 19 columns"], accent=True),
    box(1014, 180, 330, 120, f"battle_forces.csv · {n(R['battle_forces.csv'])}", fields("battle_forces.csv", 6)),
    box(1014, 320, 330, 120, f"battle_casualties.csv · {n(R['battle_casualties.csv'])}", fields("battle_casualties.csv", 6)),
    box(56, 520, 300, 120, f"factions.csv · {n(R['factions.csv'])}", fields("factions.csv", 4)),
    box(520, 520, 360, 120, f"commanders.csv · {n(R['commanders.csv'])}", fields("commanders.csv", 7)),
    box(1014, 520, 330, 120, f"sources.csv · {n(R['sources.csv'])}", fields("sources.csv", 4)),
])
arrow_specs = [
    (520, 275, 390, 275, "war_slug"),
    (1014, 240, 884, 240, "battle_slug"),
    (1014, 360, 884, 360, "battle_slug"),
    (700, 384, 700, 514, "commanders[]", True, "right"),
    (850, 384, 1030, 514, "source_slugs[]", True, "right"),
    (1179, 444, 1179, 514, "source_slug", False, "right"),
    (520, 580, 360, 580, "primary_faction_slug"),
]
schema_html = page(
    heading("SCHEMA", "Seven tables, one key: the <em style='color:var(--amber)'>slug</em>",
            f"Row counts from the {DAY} run. Every arrow is a foreign key the checker verifies; dashed ones live in battles.json.")
    + arrows(arrow_specs) + bx,
    "schema", FOOT_REAL)

# ── 3. coverage: what is filled in, and what is not ──────────────────────────────────────────

cov = S["coverage_pct"]
rows = [
    ("battles with lat/lng", pct(B["with_coords"], B["total"]), f"{n(B['with_coords'])} of {n(B['total'])}"),
    ("battles with a commander", pct(B["with_commanders"], B["total"]), f"{n(B['with_commanders'])} of {n(B['total'])}"),
    ("battles with a force estimate", pct(B["with_forces"], B["total"]), f"{n(B['with_forces'])} of {n(B['total'])}"),
    ("battles with a casualty estimate", pct(B["with_casualties"], B["total"]), f"{n(B['with_casualties'])} of {n(B['total'])}"),
    ("battles with a source reference", pct(B["with_source_refs"], B["total"]), f"{n(B['with_source_refs'])} of {n(B['total'])}"),
    ("battles with a result", pct(B["with_result"], B["total"]), f"{n(B['with_result'])} of {n(B['total'])}"),
    ("force rows that are a real range", pct(fz["rows"] - fz["point_values"], fz["rows"]),
     f"{n(fz['rows'] - fz['point_values'])} of {n(fz['rows'])} (others low = high)"),
    ("force rows with their own source", pct(fz["with_source_slug"], fz["rows"]), f"{n(fz['with_source_slug'])} of {n(fz['rows'])}"),
    ("casualty rows with their own source", pct(cz["with_source_slug"], cz["rows"]), f"{n(cz['with_source_slug'])} of {n(cz['rows'])}"),
    ("commanders with a Wikidata QID", cov["commanders.csv"]["wikidata_qid"], f"{cov['commanders.csv']['wikidata_qid']}% of {n(R['commanders.csv'])}"),
    ("commanders with a birth year", cov["commanders.csv"]["birth_year"], f"{cov['commanders.csv']['birth_year']}% of {n(R['commanders.csv'])}"),
]
bar_w = 560
cells = []
for i, (label, p, note) in enumerate(rows):
    y = 196 + i * 46
    color = "var(--bad)" if p < 10 else "var(--amber)"
    cells.append(
        f"<div style='position:absolute;left:56px;top:{y}px;width:330px;font-size:17px;text-align:right'>{esc(label)}</div>"
        f"<div style='position:absolute;left:410px;top:{y + 3}px;width:{bar_w}px;height:18px;background:#1b1917;border-radius:4px'></div>"
        f"<div style='position:absolute;left:410px;top:{y + 3}px;width:{max(bar_w * p / 100, 3):.0f}px;height:18px;background:{color};border-radius:4px'></div>"
        f"<div class='mono' style='position:absolute;left:{410 + bar_w + 18}px;top:{y + 1}px;font-size:15px;color:var(--ivory)'>{p:.1f}%</div>"
        f"<div class='mono' style='position:absolute;left:{410 + bar_w + 100}px;top:{y + 3}px;font-size:13px;color:var(--dim)'>{esc(note)}</div>")
coverage_html = page(
    heading("COVERAGE", "What is filled in, <em style='color:var(--amber)'>and what is not</em>",
            f"From check_dataset.py --stats. Red: under 10%. "
            + (f"All force and casualty rows: confidence = {next(iter(fz['confidence']))}."
               if len(fz["confidence"]) == 1 and fz["confidence"].keys() == cz["confidence"].keys() else ""))
    + "".join(cells),
    "coverage", FOOT_REAL)

write_pages(HERE, {"hero": hero_html, "schema": schema_html, "coverage": coverage_html})
