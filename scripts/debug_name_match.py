"""Analyze name mismatches between Wikidata records and DB records."""
import sys
sys.path.insert(0, ".")

from scrapers.tourism import scrape_wikidata_tourism
from database.connection import fetch_all, initialize_database

initialize_database()

# Get Wikidata records with valid TN coords
wiki = scrape_wikidata_tourism()
valid = []
for _, row in wiki.iterrows():
    try:
        lat, lon = float(row["latitude"]), float(row["longitude"])
        if 7.9 <= lat <= 13.7 and 76.0 <= lon <= 80.6:
            valid.append({
                "name": row["place_name"].strip().lower(),
                "district": row["district"].strip().lower(),
                "lat": lat, "lon": lon,
            })
    except Exception:
        pass

# Get DB records
db = fetch_all("SELECT place_name, district FROM places WHERE latitude IS NULL")
db_set = set()
for r in db:
    db_set.add((r["place_name"].strip().lower(), r["district"].strip().lower()))

print("Wikidata valid TN records:", len(valid))
print("DB records missing coords:", len(db_set))

matched = 0
unmatched_wiki = []
for v in valid:
    if (v["name"], v["district"]) in db_set:
        matched += 1
    else:
        unmatched_wiki.append(v)

print("Exact matches:", matched)
print()
print("Unmatched Wikidata samples (name | district):")
for u in unmatched_wiki[:20]:
    print(f"  {u['name']:55s} | {u['district']}")

# Also show some DB names for comparison
print()
print("Sample DB place names in Nagapattinam (for comparison):")
for r in db:
    if r["district"].lower() == "nagapattinam":
        print(f"  DB: {r['place_name']}")
