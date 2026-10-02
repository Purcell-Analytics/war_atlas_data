// Load The War Atlas nested battles.json in Node 18+ (no dependencies) and build GeoJSON.
import { readFile } from "node:fs/promises";

// Reads straight from GitHub. Set WAR_ATLAS_BASE to a local folder (ending in /) to use a clone.
const BASE = process.env.WAR_ATLAS_BASE ?? "https://raw.githubusercontent.com/Purcell-Analytics/war_atlas_data/main/";
const text = BASE.startsWith("http")
  ? await (await fetch(BASE + "battles.json")).text()
  : await readFile(BASE + "battles.json", "utf8");
const battles = JSON.parse(text);

// One GeoJSON point per battle that has coordinates (lat/lng are null when unknown).
const geojson = {
  type: "FeatureCollection",
  features: battles
    .filter((b) => b.lat !== null && b.lng !== null)
    .map((b) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [b.lng, b.lat] },
      properties: { slug: b.slug, title: b.title, year: b.year, precision: b.coord_precision },
    })),
};
console.log(`${battles.length} battles, ${geojson.features.length} as GeoJSON points`);

// Each battle carries its own forces[], casualties[], commanders[] and source_slugs[].
const b = battles.find((x) => x.slug === "battle_of_ayacucho_b");
console.log(b.title, b.year, b.date_iso);
for (const f of b.forces) console.log(`  force  ${f.side}: ${f.strength_low}-${f.strength_high}`);
for (const c of b.casualties) console.log(`  losses ${c.side}: ${c.casualties_low}-${c.casualties_high}`);
console.log(`  ${b.commanders.length} commanders, ${b.source_slugs.length} source references`);
