# The War Atlas — Open Dataset

Structured facts from [The War Atlas](https://thewaratlas.co) battles catalogue: **3,010 battles across 493 wars**, with dates, coordinates (with precision provenance), results, source-cited force-strength and casualty ranges, commanders, factions, and source references.

This repo mirrors the canonical dataset published at **[thewaratlas.co/data](https://thewaratlas.co/data)** — the live site regenerates these files as the catalogue expands, so the site copy may be newer than this mirror. See `manifest.json` for the version stamp of this snapshot.

## Files

| File | Rows | One row per |
|---|---|---|
| `battles.csv` | 3,010 | Battle — slug, title, war, campaign, year, dates, location, lat/lng with coordinate precision + source provenance, result, intensity, confidence, Wikidata QID, Wikipedia URL, canonical URL, `is_indexable` honesty flag |
| `battle_forces.csv` | 3,905 | Force-strength estimate — battle, side, low–high range, confidence, source |
| `battle_casualties.csv` | 2,713 | Casualty estimate — battle, side, low–high range, confidence, source |
| `wars.csv` | 493 | War — slug, title, era, period, start/end years, status, Wikidata QID, URL |
| `commanders.csv` | 8,012 | Commander — slug, name, primary faction, birth/death years, Wikidata QID, URL |
| `factions.csv` | 425 | Faction — slug, name, Wikidata QID, URL |
| `sources.csv` | 19,020 | Source reference — slug, type, title, identifier |
| `battles.json` | 3,010 | Nested battle records: forces[], casualties[], commanders[], source slugs[] |
| `manifest.json` | — | Row counts, generation timestamp, version, license, citation string |

## Honest ranges, not point estimates

Force and casualty figures are kept as **low–high ranges with per-row confidence levels and source references**, exactly as harvested — no false precision. Battles with no reliable figures simply have no rows in the sub-files; nothing is padded or imputed. Coordinates carry `coord_precision` (exact vs. place-level vs. approximate) and `coord_source` provenance.

## Provenance

Entity data is normalized largely from Wikidata (CC0) and Wikipedia infoboxes, cross-linked into a single relational catalogue. **This dataset contains structured facts only** — harvested Wikipedia prose (CC BY-SA) is deliberately excluded so the compilation can be licensed CC BY 4.0.

## License & attribution

[**CC BY 4.0**](https://creativecommons.org/licenses/by/4.0/). You may share and adapt this data for any purpose, including commercially, **with attribution**:

> Data: [The War Atlas](https://thewaratlas.co) — thewaratlas.co, CC BY 4.0

## Citation

```
The War Atlas (2026). The War Atlas Open Dataset [Data set].
https://thewaratlas.co/data
```

## Explore the data

Every row links back to a live, human-readable page — interactive battle maps with campaign playback, commander timelines, and cross-cuts by era, theater, year, and faction — at [thewaratlas.co](https://thewaratlas.co).
