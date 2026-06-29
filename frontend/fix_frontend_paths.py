"""
fix_frontend_paths.py
=========================
Run from frontend/ during deploy. Rewrites hardcoded fetch('/api/...')
calls to fetch('/mmc/api/...') across every known frontend source file
that needs it. Idempotent — safe to run on every deploy even if paths
are already correct.
"""
import os

FILES = [
    'src/api/scorecard.js',
    'src/pages/Dashboard.jsx',
    'src/pages/Comparison.jsx',
    'src/pages/Preview.jsx',
    'src/pages/Reports.jsx',
    'src/pages/EmployeeDetail.jsx',
    'src/components/KPIWeightManager.jsx',
    'src/components/layout/Header.jsx',
    'src/components/layout/Sidebar.jsx',
]

changed = []
for f in FILES:
    if not os.path.exists(f):
        continue
    content = open(f).read()
    new = content.replace("fetch('/api/", "fetch('/mmc/api/")
    new = new.replace('fetch("/api/', 'fetch("/mmc/api/')
    new = new.replace("fetch(`/api/", "fetch(`/mmc/api/")
    if "'/api'" in new:
        new = new.replace("'/api'", "'/mmc/api'")
    if content != new:
        open(f, 'w').write(new)
        changed.append(f)

if changed:
    print(f'Path-fixed: {changed}')
else:
    print('No /api/ path fixes needed (already correct).')