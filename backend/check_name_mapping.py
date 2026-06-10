"""
Run from backend/: python check_name_mapping.py
Shows all ViaSocket name mappings and flags likely mismatches.
"""
import sqlite3, os, difflib

DB_PATH = os.path.join(os.path.dirname(__file__), 'scorecard.db')

# Hardcoded Conversion AdminIDs from Dashboard DEPT_MAP
CONV_IDS = {
    17,19,107,148,172,303,304,315,322,323,331,336,338,
    344,346,350,351,352,359,370,377,389,397,404,415,423,
    453,454,486,489,491,493,495,507,542,544,582,856,861,
    865,868,879,908,909,
}

try:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    mappings = conn.execute(
        "SELECT viasocket_name, admin_id, match_method, confidence, sql_admin_name "
        "FROM viasocket_name_map ORDER BY match_method, viasocket_name"
    ).fetchall()
    conn.close()
except Exception as e:
    print(f"Cannot read scorecard.db: {e}")
    exit(1)

print(f"\n{'='*70}")
print(f"  VIASOCKET NAME MAPPINGS  ({len(mappings)} total)")
print(f"{'='*70}")
print(f"{'VIASOCKET NAME':<28} {'METHOD':<10} {'CONF':>5}  {'SQL SERVER NAME':<28} {'IN_CONV':>7}")
print(f"{'-'*70}")

issues = []
for m in mappings:
    vs_name   = m['viasocket_name']
    admin_id  = m['admin_id']
    method    = m['match_method']
    conf      = m['confidence']
    sql_name  = m['sql_admin_name'] or '—'
    in_conv   = '✅' if admin_id in CONV_IDS else '—'

    # Flag potential issues
    flag = ''
    if method == 'synthetic':
        flag = '⚠ UNMATCHED'
        issues.append((vs_name, admin_id, method, sql_name, 'No SQL Server match found'))
    elif method == 'fuzzy' and conf < 0.88:
        flag = '⚠ LOW CONF'
        issues.append((vs_name, admin_id, method, sql_name, f'Fuzzy confidence only {conf:.2f}'))

    color_start = '\033[93m' if '⚠' in flag else '\033[92m' if method=='exact' else ''
    color_end   = '\033[0m' if color_start else ''
    print(f"{color_start}{vs_name:<28} {method:<10} {conf:>5.2f}  {sql_name:<28} {in_conv:>7}  {flag}{color_end}")

print(f"\n{'='*70}")
print(f"  ISSUES REQUIRING ATTENTION ({len(issues)})")
print(f"{'='*70}")
if issues:
    for vs, aid, method, sql, reason in issues:
        print(f"  ⚠  '{vs}' (AdminID={aid}) — {reason}")
        print(f"     SQL matched: {sql}")
        print(f"     Fix: python -c \"import name_mapper; name_mapper.set_manual_mapping('{vs}', CORRECT_ADMIN_ID)\"")
        print()
else:
    print("  ✅ All names matched successfully!")

print(f"\n{'='*70}")
print("  HOW TO FIX A WRONG MATCH")
print(f"{'='*70}")
print("  python -c \"")
print("  import name_mapper")
print("  name_mapper.set_manual_mapping('Bharti Bhavsar', 336)  # correct AdminID")
print("  \"")