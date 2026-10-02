"""Load The War Atlas dataset with pandas and answer three questions. pip install pandas"""
import os

import pandas as pd

# Reads straight from GitHub. Set WAR_ATLAS_BASE to a local folder (ending in /) to use a clone.
BASE = os.environ.get("WAR_ATLAS_BASE", "https://raw.githubusercontent.com/Purcell-Analytics/war_atlas_data/main/")


def load(name):
    # keep_default_na=False: only a truly empty cell is missing, so a side named "NA" stays a string.
    return pd.read_csv(BASE + name, keep_default_na=False, na_values=[""])


battles, forces, wars = load("battles.csv"), load("battle_forces.csv"), load("wars.csv")

print(f"{len(battles):,} battles, {len(wars):,} wars listed, {battles.war_slug.nunique():,} wars with at least one battle")

mapped = battles.dropna(subset=["lat", "lng"])
print(f"{len(mapped):,} battles have coordinates:", mapped.coord_precision.value_counts().to_dict())

# Largest force-strength estimates, joined back to the battle.
top = (forces.merge(battles[["slug", "title", "year"]], left_on="battle_slug", right_on="slug")
       .nlargest(5, "strength_high")[["title", "year", "side", "strength_low", "strength_high"]])
print(top.to_string(index=False))
