"""Check for web scraping artifact records in the database."""
import sys
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from database.connection import fetch_all, initialize_database
initialize_database()

# Check for common web navigation junk
junk_names = [
    "Social Media Links", "Site Map", "Administrative Setup", "Directory",
    "NOTICES", "MEDIA CORNER", "Home", "Contact Us", "About Us", "Feedback",
    "Downloads", "Gallery", "Photo Gallery", "Login", "Register",
    "Disclaimer", "Copyright", "Privacy Policy", "Terms",
]

junk = fetch_all(
    "SELECT place_name, district FROM places WHERE place_name IN ({})".format(
        ",".join(["?"] * len(junk_names))
    ),
    tuple(junk_names),
)
print(f"Junk web navigation records found: {len(junk)}")
for r in junk:
    print(f"  {r['place_name']:40s} | {r['district']}")

# Check how many start with number prefix (HR&CE temple format)
numbered = fetch_all(
    "SELECT COUNT(*) as n FROM places WHERE place_name GLOB '[0-9]*'"
)
print(f"\nRecords starting with number: {numbered[0]['n']}")

# Show source distribution  
sources = fetch_all("""
    SELECT s.source_name, COUNT(*) as cnt,
           SUM(CASE WHEN p.latitude IS NOT NULL THEN 1 ELSE 0 END) as with_coords
    FROM places p
    JOIN sources s ON p.source_id = s.source_id
    GROUP BY p.source_id
    ORDER BY cnt DESC
""")
print("\nSource distribution:")
for s in sources:
    print(f"  {s['source_name']:55s} | count: {s['cnt']:5d} | with_coords: {s['with_coords']}")

# Show sample names from each source
print("\n--- Sample names from TN Tourism directory ---")
tourism_dir = fetch_all("""
    SELECT p.place_name FROM places p
    JOIN sources s ON p.source_id = s.source_id
    WHERE s.source_name = 'Tamil Nadu Tourism destination directory'
    LIMIT 20
""")
for r in tourism_dir:
    print(f"  {r['place_name']}")

print("\n--- Sample names from District portals ---")
district_portals = fetch_all("""
    SELECT p.place_name FROM places p
    JOIN sources s ON p.source_id = s.source_id
    WHERE s.source_name = '38 Tamil Nadu district administration tourism portals'
    LIMIT 20
""")
for r in district_portals:
    print(f"  {r['place_name']}")

print("\n--- Sample names from Government tourism ---")
govt = fetch_all("""
    SELECT p.place_name FROM places p
    JOIN sources s ON p.source_id = s.source_id
    WHERE s.source_name = 'Tamil Nadu government tourism-related services'
    LIMIT 20
""")
for r in govt:
    print(f"  {r['place_name']}")
