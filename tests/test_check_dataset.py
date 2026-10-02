"""Tests for scripts/check_dataset.py. Standard library only: python3 -m unittest discover -s tests -v

Each test writes a tiny, FICTIONAL two-battle dataset (made-up slugs, not real history) to a temp
directory, breaks exactly one thing, and asserts the named check fails. A checker whose checks
cannot fail is decoration, so every check here is proven able to go red.
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_dataset as cd  # noqa: E402

SITE = "https://thewaratlas.co/"


def battle(slug, war, year, lat, lng, qid, **kw):
    row = {"slug": slug, "title": slug.replace("_", " ").title(), "war_slug": war, "campaign_slug": "",
           "year": str(year), "date_iso": f"{year}-05-01", "date_display": f"May 1, {year}", "location": "",
           "lat": lat, "lng": lng, "coord_precision": "exact" if lat else "", "coord_source": "battle_p625" if lat else "",
           "result": "", "intensity": "40", "confidence_level": "", "is_indexable": "True", "wikidata_qid": qid,
           "wikipedia_url": f"https://en.wikipedia.org/wiki/{slug}", "url": f"{SITE}battles/{slug}"}
    row.update(kw)
    return row


def fixture() -> dict:
    """A valid fictional dataset. Tests mutate a copy of this."""
    return {
        "battles.csv": [battle("fictional_ridge_b", "fictional_war", 1801, "10.5", "20.25", "Q900001"),
                        battle("fictional_ford_b", "fictional_war", 1802, "", "", "Q900002")],
        "battle_forces.csv": [{"battle_slug": "fictional_ridge_b", "side": "Blue", "strength_low": "1000",
                               "strength_high": "1500", "confidence": "medium", "source_slug": "src_a"}],
        "battle_casualties.csv": [{"battle_slug": "fictional_ridge_b", "side": "Blue", "casualties_low": "100",
                                   "casualties_high": "100", "confidence": "low", "source_slug": ""}],
        "wars.csv": [{"slug": "fictional_war", "title": "Fictional War", "era_slug": "imperial", "period": "1801-1802",
                      "start_year": "1801", "end_year": "1802", "status": "modeled", "wikidata_qid": "Q900000",
                      "url": f"{SITE}wars/fictional_war"}],
        "commanders.csv": [{"slug": "gen_example", "name": "Gen. Example", "primary_faction_slug": "blue_faction",
                            "birth_year": "1760", "death_year": "", "wikidata_qid": "", "url": f"{SITE}commanders/gen_example"}],
        "factions.csv": [{"slug": "blue_faction", "name": "Blue Faction", "wikidata_qid": "Q900010", "url": f"{SITE}factions/blue_faction"}],
        "sources.csv": [{"slug": "src_a", "source_type": "monograph", "title": "A Fictional Book", "url": ""}],
    }


def to_json(t: dict) -> list:
    out = []
    for b in t["battles.csv"]:
        j = dict(b)
        j["year"], j["intensity"] = int(b["year"]), int(b["intensity"])
        j["lat"] = float(b["lat"]) if b["lat"] else None
        j["lng"] = float(b["lng"]) if b["lng"] else None
        j["is_indexable"] = b["is_indexable"] == "True"
        j["forces"] = [{"side": f["side"], "strength_low": int(f["strength_low"]), "strength_high": int(f["strength_high"]),
                        "confidence": f["confidence"], "source_slug": f["source_slug"]}
                       for f in t["battle_forces.csv"] if f["battle_slug"] == b["slug"]]
        j["casualties"] = [{"side": c["side"], "casualties_low": int(c["casualties_low"]), "casualties_high": int(c["casualties_high"]),
                            "confidence": c["confidence"], "source_slug": c["source_slug"]}
                           for c in t["battle_casualties.csv"] if c["battle_slug"] == b["slug"]]
        j["commanders"] = [{"slug": "gen_example", "name": "Gen. Example", "side": "Blue", "rank": ""}] if b["slug"] == "fictional_ridge_b" else []
        j["source_slugs"] = ["src_a"] if b["slug"] == "fictional_ridge_b" else []
        out.append(j)
    return out


def write(d: Path, t: dict, json_rows: list | None = None) -> None:
    for f, rows in t.items():
        with (d / f).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cd.SCHEMA[f])
            w.writeheader()
            w.writerows(rows)
    json_rows = to_json(t) if json_rows is None else json_rows
    (d / "battles.json").write_text(json.dumps(json_rows), encoding="utf-8")
    files = {f: {"rows": len(rows)} for f, rows in t.items()}
    files["battles.json"] = {"rows": len(json_rows)}
    (d / "manifest.json").write_text(json.dumps({"files": files}), encoding="utf-8")


class CheckDatasetTests(unittest.TestCase):
    def run_on(self, t: dict, json_rows: list | None = None, floors: dict | None = None):
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp), t, json_rows)
            report, _ = cd.run_checks(Path(tmp), floors={} if floors is None else floors)
        return report

    def assertFails(self, t: dict, check: str, **kw):
        failed = self.run_on(t, **kw).failed
        self.assertIn(check, failed, f"expected {check} to fail; failed checks: {failed}")

    def test_valid_fixture_passes_every_check(self):
        report = self.run_on(fixture())
        self.assertEqual(report.failed, [])
        self.assertGreater(len(report.results), 60)

    def test_real_snapshot_passes(self):
        report, _ = cd.run_checks(cd.ROOT)
        self.assertEqual(report.failed, [])

    def test_row_floor(self):
        self.assertFails(fixture(), "rows.floor[battles.csv]", floors={"battles.csv": 3})

    def test_manifest_row_count_mismatch(self):
        t = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp), t)
            m = json.loads((Path(tmp) / "manifest.json").read_text())
            m["files"]["wars.csv"]["rows"] = 99
            (Path(tmp) / "manifest.json").write_text(json.dumps(m))
            failed = cd.run_checks(Path(tmp), floors={})[0].failed
        self.assertIn("rows.match_manifest[wars.csv]", failed)

    def test_missing_required_field(self):
        t = fixture()
        t["battles.csv"][0]["title"] = ""
        self.assertFails(t, "required[battles.csv]")

    def test_lat_out_of_range(self):
        t = fixture()
        t["battles.csv"][0]["lat"] = "95.0"
        self.assertFails(t, "coords.in_range")

    def test_lng_out_of_range(self):
        t = fixture()
        t["battles.csv"][0]["lng"] = "-181"
        self.assertFails(t, "coords.in_range")

    def test_lat_without_lng(self):
        t = fixture()
        t["battles.csv"][0]["lng"] = ""
        self.assertFails(t, "coords.both_or_neither")

    def test_null_island(self):
        t = fixture()
        t["battles.csv"][0].update(lat="0", lng="0")
        self.assertFails(t, "coords.not_null_island")

    def test_duplicate_battle_slug(self):
        t = fixture()
        t["battles.csv"][1]["slug"] = "fictional_ridge_b"
        self.assertFails(t, "unique.slug[battles.csv]")

    def test_duplicate_battle_qid(self):
        t = fixture()
        t["battles.csv"][1]["wikidata_qid"] = "Q900001"
        self.assertFails(t, "unique.battle_qid")

    def test_battle_points_at_unknown_war(self):
        t = fixture()
        t["battles.csv"][1]["war_slug"] = "no_such_war"
        self.assertFails(t, "fk.battle_war")

    def test_force_points_at_unknown_battle(self):
        t = fixture()
        t["battle_forces.csv"][0]["battle_slug"] = "no_such_battle"
        self.assertFails(t, "fk.battle[battle_forces.csv]")

    def test_force_points_at_unknown_source(self):
        t = fixture()
        t["battle_forces.csv"][0]["source_slug"] = "no_such_source"
        self.assertFails(t, "fk.source[battle_forces.csv]")

    def test_commander_points_at_unknown_faction(self):
        t = fixture()
        t["commanders.csv"][0]["primary_faction_slug"] = "no_such_faction"
        self.assertFails(t, "fk.commander_faction")

    def test_json_source_not_in_sources(self):
        t = fixture()
        rows = to_json(t)
        rows[0]["source_slugs"] = ["no_such_source"]
        self.assertFails(t, "fk.json_source", json_rows=rows)

    def test_low_above_high(self):
        t = fixture()
        t["battle_casualties.csv"][0]["casualties_low"] = "500"
        self.assertFails(t, "range.low_le_high[battle_casualties.csv]", json_rows=to_json(fixture()))

    def test_bad_qid(self):
        t = fixture()
        t["wars.csv"][0]["wikidata_qid"] = "900000"
        self.assertFails(t, "types.qid[wars.csv]")

    def test_date_iso_disagrees_with_year(self):
        t = fixture()
        t["battles.csv"][0]["date_iso"] = "1799-05-01"
        self.assertFails(t, "types.battles.date_iso_matches_year")

    def test_json_drifts_from_csv(self):
        t = fixture()
        rows = to_json(t)
        rows[0]["title"] = "Something Else"
        self.assertFails(t, "json.scalars_match_csv", json_rows=rows)

    def test_json_force_drifts_from_csv(self):
        t = fixture()
        rows = to_json(t)
        rows[0]["forces"][0]["strength_high"] = 9999
        self.assertFails(t, "json.forces_match_csv", json_rows=rows)

    def test_header_drift(self):
        t = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp), t)
            p = Path(tmp) / "factions.csv"
            p.write_text(p.read_text().replace("wikidata_qid", "qid", 1))
            failed = cd.run_checks(Path(tmp), floors={})[0].failed
        self.assertIn("schema.header[factions.csv]", failed)

    def test_cli_exits_nonzero_on_failure(self):
        t = fixture()
        t["battles.csv"][0]["lat"] = "123"
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp), t)
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                code = cd.main([tmp])
        self.assertEqual(code, 1)
        self.assertIn("FAIL  coords.in_range", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
