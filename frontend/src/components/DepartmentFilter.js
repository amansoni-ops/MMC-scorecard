/*
  DEPARTMENT DROPDOWN — paste this block into Dashboard.jsx

  Usage: Add <DeptFilter ... /> next to the existing sort buttons.
  
  Departments:
    - All         → show all employees, all KPIs
    - Conversion  → employees using Post Conversion + Delayed + Missing Status KPIs
    - IT          → attendance KPIs only (Leaves, Late, Early, Independence)
    - Communication → same as IT

  Until the Beyond Key dept mapping arrives, AdminIDs are manually assigned below.
  Update DEPT_MAP with the actual AdminIDs once you receive the list.
*/

// ─── 1. Add this constant near the top of Dashboard.jsx (after imports) ───────

export const DEPT_MAP = {
  // Conversion team — these employees handle orders
  // Populated from April 2026 data. Update with full list from Beyond Key.
  Conversion: [
    172, 303, 304, 315, 322, 323, 331, 336, 338, 344, 346, 350, 351,
    352, 359, 370, 377, 389, 397, 404, 415, 423, 453, 454, 486, 489,
    491, 493, 495, 507, 542, 544, 582, 856, 861, 865, 868, 879, 908,
    909, 17, 19, 107, 148, 370,
  ],
  // IT + Communication — attendance-only scoring
  // Add their AdminIDs here once Beyond Key confirms
  IT:            [],
  Communication: [],
}

export const DEPT_KPI_FILTER = {
  All:          null,                                          // show all KPIs
  Conversion:   ['post_conversion', 'delayed_conversion', 'missing_status'],
  IT:           ['leaves', 'late_comings', 'early_leavings', 'independence'],
  Communication:['leaves', 'late_comings', 'early_leavings', 'independence'],
}

// ─── 2. Add this component inside Dashboard.jsx ───────────────────────────────

/*
function DeptFilter({ value, onChange }) {
  const opts = [
    { key: 'All',          label: 'All Departments', icon: '🏢' },
    { key: 'Conversion',   label: 'Conversion',       icon: '🔄' },
    { key: 'IT',           label: 'IT Department',    icon: '💻' },
    { key: 'Communication',label: 'Communication',    icon: '📞' },
  ]
  const [open, setOpen] = useState(false)
  const cur = opts.find(o => o.key === value) || opts[0]

  return (
    <div className="relative">
      <button onClick={() => setOpen(o => !o)}
        className="btn btn-secondary flex items-center gap-2"
        style={{ minWidth: 170 }}>
        <span>{cur.icon}</span>
        <span className="flex-1 text-left">{cur.label}</span>
        <ChevronDown size={13} style={{ opacity: 0.5 }}/>
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 rounded-xl border shadow-lg z-20"
          style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', minWidth: 190 }}>
          {opts.map(o => (
            <button key={o.key}
              onClick={() => { onChange(o.key); setOpen(false) }}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left transition-colors first:rounded-t-xl last:rounded-b-xl"
              style={{
                background: value === o.key ? 'var(--primary-soft)' : 'transparent',
                color: value === o.key ? 'var(--primary)' : 'var(--text)',
                fontWeight: value === o.key ? 600 : 400,
              }}>
              <span>{o.icon}</span> {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
*/

// ─── 3. Add state + filter logic in Dashboard() ───────────────────────────────

/*
const [dept, setDept] = useState('All')

// Apply dept filter to employee list:
const deptFiltered = employees.filter(emp => {
  if (dept === 'All') return true
  const ids = DEPT_MAP[dept]
  if (!ids || ids.length === 0) return dept === 'Conversion' // fallback
  return ids.includes(emp.admin_id)
})

// Then apply search + tier on top of deptFiltered (replace employees with deptFiltered):
const filtered = applySort(
  deptFiltered
    .filter(e => filter === 'ALL' || e.tier?.grade === filter)
    .filter(e => !search || (e.employee_name||'').toLowerCase().includes(search.toLowerCase()))
)
*/

// ─── 4. Add <DeptFilter> in the table header controls row ─────────────────────
/*
<DeptFilter value={dept} onChange={setDept}/>
*/

// ─── 5. Pass visible KPI list to EmpRow based on dept ────────────────────────
/*
const visibleKPIs = DEPT_KPI_FILTER[dept]
  ? kpis.filter(k => k.is_active && DEPT_KPI_FILTER[dept].includes(k.key))
  : kpis.filter(k => k.is_active)

// In EmpRow prop: kpis={visibleKPIs}
*/
