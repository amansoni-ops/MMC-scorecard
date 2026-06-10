"""
Run this ONCE after fixing the SQL Server password.
cd backend && python fix_name_mappings.py
"""
import sqlite3, os, sys
DB_PATH = os.path.join(os.path.dirname(__file__), 'scorecard.db')

print("="*60)
print("STEP 1: Clear all synthetic (broken) mappings")
print("="*60)
with sqlite3.connect(DB_PATH) as c:
    count = c.execute("SELECT COUNT(*) FROM viasocket_name_map WHERE match_method='synthetic'").fetchone()[0]
    c.execute("DELETE FROM viasocket_name_map WHERE match_method='synthetic'")
    print(f"  Deleted {count} synthetic mappings.")

print("\n" + "="*60)
print("STEP 2: Verify SQL Server is reachable")
print("="*60)
try:
    from db import execute_query
    rows = execute_query("SELECT COUNT(*) AS cnt FROM Admin WHERE Flag_Active=1")
    print(f"  SQL Server OK — {rows[0]['cnt']} active admins found")
except Exception as e:
    print(f"  ERROR: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("STEP 3: Apply known manual overrides first")
print("="*60)
from name_mapper import set_manual_mapping, init_name_map_table
init_name_map_table()

KNOWN_MAPPINGS = {
    'Aarti Jagtap'        : 303,
    'Abhishek Gour Reckon': 172,
    'Anchal patidar'      : 907,
    'Antim Rathore'       : 453,
    'Archita Neema'       : 322,
    'Asif Khan'           : 861,
    'Avani Jhinjoria'     : 120,
    'Avni Kalra'          : 493,
    'Ayushi Modi'         : 346,
    'Bhagyashree Patel'   : 856,
    'Bharti Bakriya'      : 912,
    'Bharti Bhavsar'      : 336,   # SQL has "Bharti Bhawsar"
    'Bhumika Singh'       : 928,
    'Chanchal Keshariya'  : 871,
    'Deepak Kumar Namdeo' : 315,
    'Deepak Mishra'       : 389,
    'Deepak Parmar'       : 467,
    'Devvani Tiwari'      : 489,
    'Ekta Hirke'          : 344,
    'Esha Kumari'         : 491,
    'Gautam bhawsar'      : 934,
    'Gunjan Agrawal'      : 944,
    'Harsh mourya'        : 908,
    'Harshita Hardiya'    : 414,
    'Ishika Sharma'       : 514,
    'Jayesh Sharma'       : 933,
    'Kanishk Sharma'      : 507,
    'Khushi Yadav'        : 56,
    'Kritika Nema'        : 445,
    'Lavisha chandani'    : 935,
    'Laxmi Sachdev'       : 937,
    'Mahima Pardeshi'     : 370,
    'Mohammad Altaf'      : 417,
    'Muskan Gangrade'     : 936,
    'Naveen Dange'        : 931,
    'Nikita Lalawat'      : 495,
    'Nikita Malviya'      : 423,
    'Nousheen khan'       : 909,
    'Pooja Rathore'       : 894,
    'Prachi Borde'        : 304,
    'Pratibha Tomar'      : 107,
    'Preeti Shinde'       : 19,
    'Rahul Gour'          : 323,
    'Rajat Mehra'         : 377,
    'Rajat Pawar'         : 868,
    'Ronak Pal'           : 454,
    'Roshani Panchore'    : 331,
    'Sakina Ratlamwala'   : 922,
    'Sakshi Jatav'        : 530,
    'Sarita Jaiswal'      : 415,
    'Sheetal chouhan'     : 929,
    'Shivani Rathore'     : 338,
    'Shruti Garg'         : 911,
    'Srushti Gupta'       : 903,
    'Taha Rajodwala'      : 486,
    'Vanya Khanchandani'  : 410,
    'Varsha Yadav'        : 409,
    'Vibhooti Badera'     : 945,
    'Yadeep Songara'      : 930,
    'Yash Purohit'        : 403,
    'Yogesh Uikey'        : 913,
    'nimmi chauhan'       : 879,
    'Aman Soni'           : 809,
}

for vs_name, admin_id in KNOWN_MAPPINGS.items():
    set_manual_mapping(vs_name, admin_id)
    print(f"  ✅  '{vs_name}' → {admin_id}")

print(f"\n  Applied {len(KNOWN_MAPPINGS)} manual mappings.")

print("\n" + "="*60)
print("STEP 4: Auto-match remaining names via fuzzy matching")
print("="*60)
try:
    from viasocket   import get_leaves_for_month
    from name_mapper import resolve
    from datetime    import datetime

    now  = datetime.now()
    rows = get_leaves_for_month(now.month, now.year)
    print(f"  {len(rows)} employees from ViaSocket")

    matched = 0
    for row in rows:
        name = (row.get('name') or '').strip()
        if not name: continue
        result = resolve(name)
        if result['match_method'] != 'synthetic':
            matched += 1

    print(f"  Auto-matched: {matched} / {len(rows)}")
except Exception as e:
    print(f"  Warning: {e}")

print("\n" + "="*60)
print("STEP 5: Final summary")
print("="*60)
with sqlite3.connect(DB_PATH) as c:
    for method in ['manual','exact','fuzzy','synthetic']:
        cnt = c.execute(f"SELECT COUNT(*) FROM viasocket_name_map WHERE match_method=?", (method,)).fetchone()[0]
        icon = '✅' if method != 'synthetic' else '⚠ '
        print(f"  {icon}  {method:<12}: {cnt}")

    synth = c.execute("SELECT viasocket_name FROM viasocket_name_map WHERE match_method='synthetic'").fetchall()
    if synth:
        print(f"\n  Still unmatched (need manual fix):")
        for r in synth:
            print(f"    - {r[0]}")

    # Clear score cache
    c.execute("DELETE FROM score_cache")
    print("\n  Score cache cleared.")

print("\n✅  DONE. Restart Flask and reload the dashboard.")
print("="*60)