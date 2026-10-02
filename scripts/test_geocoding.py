"""Test geocoding with smart query variants on the same sample."""
import sys
import time
import re

sys.path.insert(0, ".")
from database.connection import fetch_all, initialize_database
from services.location.geocoding import geocode_location

initialize_database()

places = [
    ("GangaiKondaCholapuram Temple", "Ariyalur"),
    ("Field Fossil Museum - Varanavasi", "Ariyalur"),
    ("Mamallapuram Seashore Temple", "Chengalpattu"),
    ("Vedanthangal Bird Sanctuary", "Chengalpattu"),
    ("Madurantakam Lake", "Chengalpattu"),
]

def generate_query_variants(name, district):
    variants = []
    # 1. Exact as-is
    variants.append(f"{name}, {district}")
    
    # 2. Split CamelCase (e.g. GangaiKondaCholapuram -> Gangai Konda Cholapuram)
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    if spaced != name:
        variants.append(f"{spaced}, {district}")
        
    # 3. If hyphen or dash or comma, split
    parts = re.split(r"[-–—,]", name)
    if len(parts) > 1:
        for p in parts:
            p_clean = p.strip()
            if len(p_clean) > 3:
                variants.append(f"{p_clean}, {district}")

    # 4. Remove common suffixes like " Temple", " Kovil"
    simplified = re.sub(r"\b(Temple|Kovil|Koil)\b", "", name, flags=re.I).strip()
    if simplified and simplified != name:
        variants.append(f"{simplified}, {district}")

    # Remove duplicates preserving order
    seen = set()
    deduped = []
    for v in variants:
        if v.lower() not in seen:
            seen.add(v.lower())
            deduped.append(v)
    return deduped

print("Testing smart query variants...\n")
for name, district in places:
    print(f"--- Place: '{name}' ({district}) ---")
    variants = generate_query_variants(name, district)
    found = None
    for q in variants:
        res = geocode_location(q)
        time.sleep(1.1)
        if res:
            found = (q, res)
            break
        else:
            print(f"  Tried '{q}' -> None")
    if found:
        print(f"  SUCCESS! '{found[0]}' -> {found[1]}\n")
    else:
        print("  FAILED all variants\n")
