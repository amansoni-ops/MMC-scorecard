import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, ReferenceLine,
} from 'recharts'
import { useStore } from '../store/appStore'
import { MONTHS, YEARS, fmtScore, monthName } from '../utils/formatters'
import KPIWeightManager from '../components/KPIWeightManager'
import StatCard from '../components/cards/StatCard'
import {
  Search, Settings, RefreshCw, TrendingUp, Users, Trophy,
  AlertTriangle, X, Info, ChevronDown, ChevronUp,
  ArrowUpDown, ArrowUp, ArrowDown, Building2,
} from 'lucide-react'
import toast from 'react-hot-toast'

const TIER_COLOR = { A: '#10B981', B: '#F59E0B', C: '#EF4444' }

const DEPT_MAP = {
  Conversion: [
    17, 19, 107, 148, 172, 303, 304, 315, 322, 323, 331, 336, 338,
    344, 346, 350, 351, 352, 359, 370, 377, 389, 397, 404, 415, 423,
    453, 454, 486, 489, 491, 493, 495, 507, 542, 544, 582, 856, 861,
    865, 868, 879, 908, 909,
  ],
  IT:            [],
  Communication: [],
}

const DEPT_KPI_KEYS = {
  All:           null,
  Conversion:    ['post_conversion', 'delayed_conversion', 'missing_status',
                  'leaves', 'late_comings', 'early_leavings', 'independence'],
  IT:            ['leaves', 'late_comings', 'early_leavings', 'independence'],
  Email:         ['leaves', 'late_comings', 'early_leavings', 'independence'],
  Account:       ['leaves', 'late_comings', 'early_leavings', 'independence'],
  HR:            ['leaves', 'late_comings', 'early_leavings', 'independence'],
  Communication: ['leaves', 'late_comings', 'early_leavings', 'independence'],
  RND:           ['leaves', 'late_comings', 'early_leavings', 'independence'],
}

const DEPT_OPTS = [
  { key: 'All',          label: 'All Departments', icon: '🏢' },
  { key: 'Conversion',   label: 'Conversion',       icon: '🔄' },
  { key: 'IT',           label: 'IT Department',    icon: '💻' },
  { key: 'Email',        label: 'Email Team',        icon: '📧' },
  { key: 'Account',      label: 'Accounts',          icon: '💰' },
  { key: 'HR',           label: 'Human Resources',   icon: '👥' },
  { key: 'Communication',label: 'Communication',     icon: '📞' },
  { key: 'RND',          label: 'R&D',               icon: '🔬' },
]

function DeptDropdown({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const cur = DEPT_OPTS.find(o => o.key === value) || DEPT_OPTS[0]

  useEffect(() => {
    const fn = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', fn)
    return () => document.removeEventListener('mousedown', fn)
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)}
        className="btn btn-secondary flex items-center gap-2"
        style={{ minWidth: 165 }}>
        <span>{cur.icon}</span>
        <span className="flex-1 text-left text-sm">{cur.label}</span>
        <ChevronDown size={12} style={{ opacity: 0.5 }}/>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.97 }}
            transition={{ duration: 0.12 }}
            className="absolute left-0 top-full mt-1 rounded-xl border z-30 overflow-hidden"
            style={{
              background: 'var(--bg-card)',
              borderColor: 'var(--border)',
              minWidth: 185,
              boxShadow: '0 8px 24px rgba(0,0,0,0.10)',
            }}>
            {DEPT_OPTS.map(o => (
              <button key={o.key}
                onClick={() => { onChange(o.key); setOpen(false) }}
                className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-left transition-colors"
                style={{
                  background: value === o.key ? 'var(--primary-soft)' : 'transparent',
                  color: value === o.key ? '#6366F1' : 'var(--text)',
                  fontWeight: value === o.key ? 600 : 400,
                }}>
                <span style={{ fontSize: 14 }}>{o.icon}</span>
                {o.label}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function FormulaModal({ emp, onClose }) {
  if (!emp) return null
  const kpis = Object.entries(emp.kpi_breakdown || {})
  const tc = TIER_COLOR[emp.tier?.grade] ?? '#6366F1'
  return (
    <motion.div className="fixed inset-0 z-50 flex items-center justify-center"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.45)' }} onClick={onClose}/>
      <motion.div className="relative card p-6 w-[500px] max-h-[85vh] overflow-y-auto"
        initial={{ scale: 0.92, y: 12 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.92, y: 12 }}
        style={{ boxShadow: '0 24px 80px rgba(0,0,0,0.20)', background: 'var(--bg-card)' }}>
        <div className="flex items-center justify-between mb-5">
          <div>
            <p className="font-bold text-base" style={{ color: 'var(--text)' }}>Score Formula</p>
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{emp.employee_name}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg"
            style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)' }}>
            <X size={16}/>
          </button>
        </div>
        <div className="space-y-1 mb-5">
          <div className="grid grid-cols-4 gap-2 pb-2 border-b text-[10px] font-bold uppercase tracking-wider"
            style={{ color: 'var(--text-faint)', borderColor: 'var(--border)' }}>
            <span className="col-span-2">KPI</span>
            <span className="text-center">Ratio</span>
            <span className="text-right">Score</span>
          </div>
          {kpis.map(([key, kpi]) => {
            const r = kpi.success_ratio ?? 0
            const s = kpi.score ?? 0
            const has = kpi.success_ratio !== null
            return (
              <div key={key} className="grid grid-cols-4 gap-2 py-2 rounded-lg px-2"
                style={{ background: has ? 'var(--bg-hover)' : 'transparent' }}>
                <div className="col-span-2">
                  <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>{kpi.name}</p>
                  <p className="text-xs" style={{ color: 'var(--text-faint)' }}>
                    {kpi.weight?.toFixed(1)}% weight · {kpi.numerator}/{kpi.denominator}
                  </p>
                </div>
                <div className="flex flex-col items-center justify-center">
                  {has ? (
                    <>
                      <span className="text-sm font-medium" style={{ color: '#6366F1' }}>{r.toFixed(1)}%</span>
                      <div className="w-full h-1 rounded-full mt-1" style={{ background: 'var(--border)' }}>
                        <div className="h-full rounded-full" style={{ width: `${Math.min(r,100)}%`, background: '#6366F1' }}/>
                      </div>
                    </>
                  ) : <span className="text-xs" style={{ color: 'var(--text-faint)' }}>N/A</span>}
                </div>
                <div className="flex items-center justify-end">
                  <span className="text-sm font-semibold tabular-nums"
                    style={{ color: has ? tc : 'var(--text-faint)' }}>
                    {has ? s.toFixed(2) : '—'}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
        <div className="border-t pt-4 flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
          <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Total Score</p>
          <p className="text-2xl font-light tabular-nums" style={{ color: tc }}>{fmtScore(emp.total_score)}</p>
        </div>
        <div className="mt-3 p-3 rounded-lg text-xs" style={{ background: 'var(--bg-hover)', color: 'var(--text-faint)' }}>
          Total = Σ (KPI Ratio × Weight / 100) — Max 100 pts
        </div>
      </motion.div>
    </motion.div>
  )
}

function KPIDrillDown({ kpiKey, kpi, emp }) {
  const orders = kpi?.orders || []
  const o = orders[0]

  if (!orders.length) return (
    <div className="px-6 py-3 text-xs italic" style={{ color: 'var(--text-faint)' }}>
      No details available for this month.
    </div>
  )

  if (kpiKey === 'missing_status') return (
    <div className="px-6 py-3 flex gap-8 text-sm">
      <span style={{ color: 'var(--text-muted)' }}>
        Working days: <b style={{ color: 'var(--text)' }}>{o?.TotalActiveDays ?? o?.working_days ?? '—'}</b>
      </span>
      <span style={{ color: '#10B981' }}>Updated: <b>{o?.DaysWithUpdate ?? '—'}</b></span>
      <span style={{ color: '#EF4444' }}>
        Missed: <b>{o?.MissedDays ?? ((o?.TotalActiveDays ?? 0) - (o?.DaysWithUpdate ?? 0))}</b>
      </span>
    </div>
  )

  if (kpiKey === 'leaves') {
    const dates = o?.leave_dates || []
    return (
      <div className="px-6 py-3">
        <div className="flex gap-8 text-sm mb-3">
          <span style={{ color: 'var(--text-muted)' }}>
            Working days: <b style={{ color: 'var(--text)' }}>{o?.working_days ?? '—'}</b>
          </span>
          <span style={{ color: '#10B981' }}>Present: <b>{o?.present_days ?? '—'}</b></span>
          <span style={{ color: '#EF4444' }}>Leaves taken: <b>{o?.leave_days ?? '—'}</b></span>
        </div>
        {dates.length > 0 && (
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-1.5"
              style={{ color: 'var(--text-faint)' }}>Leave Dates</p>
            <div className="flex flex-wrap gap-1.5">
              {dates.map((d, i) => (
                <span key={i} className="text-xs px-2 py-0.5 rounded-lg font-medium"
                  style={{ background: '#FEE2E2', color: '#DC2626' }}>{d}</span>
              ))}
            </div>
          </div>
        )}
        {dates.length === 0 && (
          <p className="text-xs" style={{ color: '#10B981' }}>✓ No leaves taken this month</p>
        )}
      </div>
    )
  }

  if (kpiKey === 'late_comings') {
    const entries = o?.late_entries || []
    // FIXED: punch_in/shift_start values from the backend are ALREADY in
    // IST — confirmed against real Keka source data, which carries no
    // timezone marker at all and is recorded directly in IST by the
    // physical punch machine. The OLD version of this function treated
    // these as UTC (via the 'UTC' suffix the backend used to send) and
    // asked the browser to convert UTC->IST, which DOUBLE-SHIFTED an
    // already-correct time forward by +5:30 (e.g. a real 2:47 PM punch
    // displayed as 8:17 PM). The backend now sends an 'IST' suffix
    // instead of 'UTC' — this function just extracts and formats the
    // clock value directly, with NO timezone conversion at all.
    const toIST = (s) => {
      if (!s) return '—'
      // Expected format: "2026-06-19 14:47:40 IST"
      const match = /(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})/.exec(s)
      if (!match) return s
      const hours = parseInt(match[4], 10)
      const mins  = parseInt(match[5], 10)
      const period = hours >= 12 ? 'pm' : 'am'
      const displayH = hours % 12 === 0 ? 12 : hours % 12
      return `${String(displayH).padStart(2,'0')}:${String(mins).padStart(2,'0')} ${period}`
    }
    // DISPLAY-ONLY grace label: shift_start + 15 minutes, formatted the
    // same way as every other time on this card. This is NOT the real
    // backend grace threshold (which is 20 minutes) — it's purely a
    // simplified figure shown to employees, per explicit request.
    //
    // FIXED: previously read entries[0].shift_start — but that only
    // exists for employees who have at least one LATE arrival this month
    // (late_entries is empty for everyone else, causing blank grace for
    // most people), AND it's a full UTC datetime string, a different
    // format from o.shift_start. Now reads o.shift_start instead — this
    // is the person's own modal/typical shift start, present for EVERY
    // employee regardless of late history, stored as a plain 'HH:MM'
    // 24-hour string (e.g. "14:30"), NOT a UTC datetime string — parsed
    // accordingly here rather than reusing the UTC-string parsing logic
    // that caused garbled/wrong times before.
    const graceLabel = (() => {
      const shiftStartHHMM = o?.shift_start   // e.g. "14:30", always present per-person
      if (!shiftStartHHMM || shiftStartHHMM === '--') return '—'
      const match = /^(\d{1,2}):(\d{2})$/.exec(shiftStartHHMM)
      if (!match) return '—'
      const hours = parseInt(match[1], 10)
      const mins  = parseInt(match[2], 10)
      if (Number.isNaN(hours) || Number.isNaN(mins)) return '—'
      // Build a plain Date in LOCAL time terms purely as a calculation
      // aid for adding 15 minutes — no timezone conversion happens here
      // since shift_start is already the IST clock time itself, not UTC.
      const totalMins = (hours * 60 + mins + 15) % (24 * 60)
      const graceH = Math.floor(totalMins / 60)
      const graceM = totalMins % 60
      const period = graceH >= 12 ? 'pm' : 'am'
      const displayH = graceH % 12 === 0 ? 12 : graceH % 12
      return `${String(displayH).padStart(2,'0')}:${String(graceM).padStart(2,'0')} ${period}`
    })()
    return (
      <div className="px-6 py-3">
        <div className="flex gap-8 text-sm mb-3">
          <span style={{ color: 'var(--text-muted)' }}>
            Working days: <b style={{ color: 'var(--text)' }}>{o?.working_days ?? '—'}</b>
          </span>
          <span style={{ color: '#10B981' }}>On-time: <b>{o?.on_time_days ?? '—'}</b></span>
          <span style={{ color: '#EF4444' }}>Late arrivals: <b>{o?.late_days ?? '—'}</b></span>
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>Grace: {graceLabel} IST</span>
        </div>
        {entries.length > 0 ? (
          <table className="w-full text-xs">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Date', 'Shift Start (IST)', 'Actual Punch In (IST)', 'Delay'].map((h, i) => (
                  <th key={i} className="text-left py-1.5 pr-4 font-semibold"
                    style={{ color: 'var(--text-faint)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => {
                let delay = '—'
                try {
                  // FIXED: backend now sends "...IST" suffix instead of
                  // "...UTC". Since we only need the DIFFERENCE between
                  // punch_in and shift_start (both in the same IST frame),
                  // the absolute timezone doesn't matter for this
                  // subtraction — just need a format Date() parses
                  // consistently for both. Replacing ' IST' with nothing
                  // and letting Date() parse as a naive local datetime
                  // works correctly here since both sides get the same
                  // (irrelevant) local-timezone treatment, cancelling out
                  // in the subtraction.
                  const parseLocal = (s) => new Date((s || '').replace(' IST', ''))
                  const mins = Math.round(
                    (parseLocal(e.punch_in) - parseLocal(e.shift_start)) / 60000
                  )
                  if (mins > 0) delay = `+${mins} min`
                } catch {}
                return (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td className="py-1.5 pr-4 font-medium" style={{ color: 'var(--text)' }}>{e.date}</td>
                    <td className="py-1.5 pr-4 tabular-nums" style={{ color: 'var(--text-muted)' }}>
                      {toIST(e.shift_start)}
                    </td>
                    <td className="py-1.5 pr-4 tabular-nums font-medium" style={{ color: '#EF4444' }}>
                      {toIST(e.punch_in)}
                    </td>
                    <td className="py-1.5 font-bold" style={{ color: '#EF4444' }}>{delay}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        ) : (
          <p className="text-xs" style={{ color: '#10B981' }}>✓ No late arrivals this month</p>
        )}
      </div>
    )
  }

  if (kpiKey === 'early_leavings') {
    const entries = o?.early_entries || []
    return (
      <div className="px-6 py-3">
        <div className="flex gap-8 text-sm mb-3">
          <span style={{ color: 'var(--text-muted)' }}>
            Working days: <b style={{ color: 'var(--text)' }}>{o?.working_days ?? '—'}</b>
          </span>
          <span style={{ color: '#10B981' }}>Full days: <b>{o?.full_days ?? '—'}</b></span>
          <span style={{ color: '#EF4444' }}>Early exits: <b>{o?.early_days ?? '—'}</b></span>
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>Expected: 8.5h</span>
        </div>
        {entries.length > 0 ? (
          <table className="w-full text-xs">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Date', 'Expected Hours', 'Actual Hours', 'Shortfall'].map((h, i) => (
                  <th key={i} className="text-left py-1.5 pr-4 font-semibold"
                    style={{ color: 'var(--text-faint)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="py-1.5 pr-4 font-medium" style={{ color: 'var(--text)' }}>{e.date}</td>
                  <td className="py-1.5 pr-4 tabular-nums" style={{ color: 'var(--text-muted)' }}>
                    {e.expected_hours}h
                  </td>
                  <td className="py-1.5 pr-4 tabular-nums font-medium" style={{ color: '#EF4444' }}>
                    {e.actual_hours}h
                  </td>
                  <td className="py-1.5 font-bold" style={{ color: '#EF4444' }}>
                    -{e.shortfall_hrs}h
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-xs" style={{ color: '#10B981' }}>✓ No early exits this month</p>
        )}
      </div>
    )
  }

  if (kpiKey === 'independence') return (
    <div className="px-6 py-3 flex gap-8 text-sm">
      <span style={{ color: 'var(--text-muted)' }}>
        Rating: <b style={{ color: '#6366F1' }}>{o?.rating ?? 'Not rated'}</b>
      </span>
      <span style={{ color: 'var(--text-muted)' }}>
        Score: <b style={{ color: '#6366F1' }}>{o?.score_pct ?? '—'}%</b>
      </span>
      {o?.rated_by && (
        <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>Rated by: {o.rated_by}</span>
      )}
    </div>
  )

  const isDelayed = kpiKey === 'delayed_conversion'
  return (
    <div className="px-6 py-3">
      <p className="text-xs font-bold mb-2" style={{ color: 'var(--text-faint)' }}>
        {isDelayed ? 'DELIVERY DETAILS' : 'FILES WITH ISSUES'}&nbsp;
        <span className="font-normal">
          ({orders.filter(o => isDelayed ? o.status === 'Delayed' : o.issue === 'Issue').length} problem
          {' '}/ {orders.length} total)
        </span>
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Order #', 'Company', 'Completed', isDelayed ? 'ETA' : null, 'Status']
                .filter(Boolean).map((h, i) => (
                <th key={i} className="text-left py-1.5 pr-4 font-semibold"
                  style={{ color: 'var(--text-faint)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {orders.slice(0, 12).map((o, i) => {
              const bad = isDelayed ? o.status === 'Delayed' : o.issue === 'Issue'
              return (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td className="py-1.5 pr-4 font-mono" style={{ color: 'var(--text-muted)' }}>
                    {o.order_number || o.order_id}
                  </td>
                  <td className="py-1.5 pr-4 max-w-[180px] truncate" style={{ color: 'var(--text)' }}>
                    {o.company}
                  </td>
                  <td className="py-1.5 pr-4 tabular-nums" style={{ color: 'var(--text-muted)' }}>
                    {o.completed}
                  </td>
                  {isDelayed && (
                    <td className="py-1.5 pr-4 tabular-nums" style={{ color: 'var(--text-muted)' }}>
                      {o.eta || '—'}
                    </td>
                  )}
                  <td className="py-1.5">
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                      style={{ background: bad ? '#FEE2E2' : '#DCFCE7', color: bad ? '#DC2626' : '#15803D' }}>
                      {isDelayed ? (o.status || 'No ETA') : (o.issue || 'Clean')}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {orders.length > 12 && (
          <p className="text-xs mt-1" style={{ color: 'var(--text-faint)' }}>+{orders.length - 12} more</p>
        )}
      </div>
    </div>
  )
}

function EmpRow({ emp, rank, visibleKPIs, onClickName, onClickFormula }) {
  const [drill, setDrill] = useState(null)
  const tc = TIER_COLOR[emp.tier?.grade] ?? '#6366F1'
  const toggle = (k) => setDrill(drill === k ? null : k)

  return (
    <>
      <tr className="border-b" style={{ borderColor: 'var(--border)' }}
        onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
        <td className="px-4 py-3 text-xs font-mono" style={{ color: 'var(--text-faint)' }}>{rank}</td>
        <td className="px-4 py-3">
          <button onClick={() => onClickName(emp)} className="flex items-center gap-2.5 group text-left">
            <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
              style={{ background: tc }}>{emp.employee_name?.[0]}</div>
            <span className="font-medium text-sm group-hover:underline decoration-dotted"
              style={{ color: 'var(--text)' }}>{emp.employee_name}</span>
          </button>
        </td>
        <td className="px-4 py-3">
          <span className="text-xs font-bold px-2 py-0.5 rounded-full"
            style={{ background: `${tc}18`, color: tc }}>
            Tier {emp.tier?.grade}
          </span>
        </td>
        {visibleKPIs.map(k => {
          const kd       = emp.kpi_breakdown?.[k.key]
          const success  = kd?.success_ratio ?? null
          const failPct  = success !== null ? +(100 - success).toFixed(1) : null
          const failCount= kd ? (kd.denominator ?? 0) - (kd.numerator ?? 0) : 0
          const denom    = kd?.denominator ?? 0
          const isOpen   = drill === k.key
          const barColor = failPct === null ? 'var(--border)'
            : failPct <= 5  ? '#10B981'
            : failPct <= 20 ? '#F59E0B'
            : '#EF4444'
          return (
            <td key={k.key} className="px-4 py-3">
              <div className="flex items-center gap-1.5">
                <div className="flex-1">
                  <div className="flex items-center gap-1.5">
                    <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                      <div className="h-full rounded-full transition-all"
                        style={{ width: `${Math.min(failPct ?? 0, 100)}%`, background: barColor }}/>
                    </div>
                    <span className="text-xs tabular-nums w-10 text-right font-medium"
                      style={{ color: barColor }}>
                      {failPct !== null ? `${failPct.toFixed(1)}%` : '—'}
                    </span>
                  </div>
                  {denom > 0 && (
                    <p className="text-[10px] mt-0.5 tabular-nums" style={{ color: 'var(--text-faint)' }}>
                      {failCount} / {denom}
                    </p>
                  )}
                </div>
                {kd && kd.denominator > 0 && (
                  <button onClick={() => toggle(k.key)} title={`View ${k.name} details`}
                    className="p-0.5 rounded transition-colors shrink-0"
                    style={{ background: isOpen ? '#EEF2FF' : 'var(--bg-hover)', color: isOpen ? '#6366F1' : 'var(--text-faint)' }}>
                    {isOpen ? <ChevronUp size={12}/> : <ChevronDown size={12}/>}
                  </button>
                )}
              </div>
            </td>
          )
        })}
        <td className="px-4 py-3 text-right">
          <span className="text-xl font-light tabular-nums" style={{ color: tc }}>{fmtScore(emp.total_score)}</span>
        </td>
        <td className="px-3 py-3">
          <button onClick={() => onClickFormula(emp)} title="Score formula"
            className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border transition-colors"
            style={{ background: 'var(--bg-hover)', color: 'var(--text-faint)', borderColor: 'var(--border)' }}
            onMouseEnter={e => { e.currentTarget.style.background='#EEF2FF'; e.currentTarget.style.color='#6366F1' }}
            onMouseLeave={e => { e.currentTarget.style.background='var(--bg-hover)'; e.currentTarget.style.color='var(--text-faint)' }}>
            i
          </button>
        </td>
      </tr>
      {drill && (
        <tr style={{ borderBottom: '1px solid var(--border)' }}>
          <td colSpan={99} style={{ background: 'var(--bg)', padding: 0 }}>
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.18 }}>
              <KPIDrillDown kpiKey={drill} kpi={emp.kpi_breakdown?.[drill]} emp={emp}/>
            </motion.div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function Dashboard() {
  const { setEmployees, setKPIs, kpis, employees } = useStore()
  const navigate = useNavigate()
  const { selectedMonth: month, selectedYear: year,
        setSelectedMonth: setMonth, setSelectedYear: setYear } = useStore()
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [filter, setFilter]   = useState('ALL')
  const [search, setSearch]   = useState('')
  const [dept,   setDept]     = useState('All')
  const [showKPI, setShowKPI] = useState(false)
  const [formulaEmp, setFEmp] = useState(null)
  const [sortBy, setSortBy]   = useState('name_asc')
  const reqId = useRef(0)

  const fetchData = async (m, y) => {
    const id = ++reqId.current
    setLoading(true); setError(null)
    try {
      const meRes = await fetch('/api/me', { credentials: 'include' })
      if (!meRes.ok) { navigate('/login'); return }
      const [scRes, kpRes] = await Promise.all([
        fetch(`/api/scores?month=${m}&year=${y}`, { credentials: 'include' }),
        fetch('/api/kpis', { credentials: 'include' }),
      ])
      if (id !== reqId.current) return
      if (!scRes.ok) throw new Error(`HTTP ${scRes.status}`)
      const scData = await scRes.json()
      const kpData = await kpRes.json()
      setEmployees(scData.employees ?? [])
      setKPIs(kpData.kpis ?? [])
      if (!(scData.employees ?? []).length) setError(`No data for ${monthName(m)} ${y}.`)
    } catch (err) {
      if (id !== reqId.current) return
      setError(err.message); toast.error(`Load failed: ${err.message}`)
    } finally { if (id === reqId.current) setLoading(false) }
  }
  useEffect(() => { fetchData(month, year) }, [month, year])

  const deptEmployees = employees.filter(emp => {
    if (dept === 'All') return true
    if (dept === 'Conversion') return !!emp.is_conversion
    const empDept = (emp.department || '').trim()
    return empDept === dept
  })

  const kpiKeyFilter = DEPT_KPI_KEYS[dept]
  const visibleKPIs  = kpis.filter(k =>
    k.is_active && (!kpiKeyFilter || kpiKeyFilter.includes(k.key))
  )

  const applySort = (list) => {
    const arr = [...list]
    if (sortBy === 'name_asc')   return arr.sort((a,b)=>(a.employee_name||'').localeCompare(b.employee_name||''))
    if (sortBy === 'name_desc')  return arr.sort((a,b)=>(b.employee_name||'').localeCompare(a.employee_name||''))
    if (sortBy === 'score_desc') return arr.sort((a,b)=>b.total_score-a.total_score)
    if (sortBy === 'score_asc')  return arr.sort((a,b)=>a.total_score-b.total_score)
    return arr
  }

  const filtered = applySort(
    deptEmployees
      .filter(e => filter === 'ALL' || e.tier?.grade === filter)
      .filter(e => !search || (e.employee_name||'').toLowerCase().includes(search.toLowerCase()))
  )

  const stats = {
    total: deptEmployees.length,
    A: deptEmployees.filter(e=>e.tier?.grade==='A').length,
    B: deptEmployees.filter(e=>e.tier?.grade==='B').length,
    C: deptEmployees.filter(e=>e.tier?.grade==='C').length,
    avg: deptEmployees.length ? deptEmployees.reduce((s,e)=>s+(e.total_score||0),0)/deptEmployees.length : 0,
  }

  const donutData = ['A','B','C']
    .map(g=>({name:`Tier ${g}`, value:stats[g], fill:TIER_COLOR[g]}))
    .filter(d=>d.value>0)

  const SortBtn = ({ val, label }) => (
    <button onClick={() => setSortBy(val)}
      className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg transition-colors"
      style={{
        background: sortBy===val?'var(--primary-soft)':'var(--bg-hover)',
        color: sortBy===val?'#6366F1':'var(--text-muted)',
        fontWeight: sortBy===val?600:400,
      }}>
      {sortBy===val && sortBy.includes('desc') ? <ArrowDown size={11}/> :
       sortBy===val && sortBy.includes('asc') && sortBy!=='name_asc' ? <ArrowUp size={11}/> :
       <ArrowUpDown size={11}/>}
      {label}
    </button>
  )

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <select value={month} onChange={e=>setMonth(+e.target.value)} className="form-input">
            {MONTHS.map(m=><option key={m.value} value={m.value}>{m.full}</option>)}
          </select>
          <select value={year} onChange={e=>setYear(+e.target.value)} className="form-input">
            {YEARS.map(y=><option key={y} value={y}>{y}</option>)}
          </select>
          <button onClick={()=>fetchData(month,year)} className="btn btn-secondary" disabled={loading}>
            <RefreshCw size={13} className={loading?'animate-spin':''}/>{loading?'Loading…':'Refresh'}
          </button>
        </div>
        <button onClick={()=>setShowKPI(true)} className="btn btn-secondary">
          <Settings size={13}/> Configure KPIs
        </button>
      </div>

      {error && !loading && (
        <div className="flex items-start gap-3 p-4 rounded-xl border"
          style={{ background:'rgba(245,158,11,0.06)', borderColor:'rgba(245,158,11,0.3)' }}>
          <Info size={16} className="shrink-0 mt-0.5" style={{ color:'#D97706' }}/>
          <p className="text-sm" style={{ color:'var(--text)' }}>{error}</p>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Active Employees" value={stats.total} sub={`${monthName(month)} ${year}`} color="indigo" icon={Users}/>
        <StatCard label="High Performers"  value={stats.A}     sub="Tier A ≥ 90"  color="green"  icon={Trophy}/>
        <StatCard label="Needs Attention"  value={stats.C}     sub="Tier C < 60"  color="red"    icon={AlertTriangle}/>
        <StatCard label="Team Avg Score"   value={fmtScore(stats.avg)} sub="out of 100" color="amber" icon={TrendingUp}/>
      </div>

      {deptEmployees.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="card p-5">
            <p className="font-semibold text-sm mb-1" style={{ color:'var(--text)' }}>Tier Distribution</p>
            <div style={{ height: 170 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={donutData} cx="50%" cy="50%" innerRadius={45} outerRadius={72} paddingAngle={3} dataKey="value">
                    {donutData.map((d,i)=><Cell key={i} fill={d.fill}/>)}
                  </Pie>
                  <Tooltip contentStyle={{ background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:10, fontSize:13 }}/>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-around mt-2">
              {['A','B','C'].map(g=>(
                <div key={g} className="text-center">
                  <p className="text-2xl font-light" style={{ color:TIER_COLOR[g] }}>{stats[g]}</p>
                  <p className="text-xs" style={{ color:'var(--text-faint)' }}>Tier {g}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="card p-5 lg:col-span-2">
            <p className="font-semibold text-sm mb-1" style={{ color:'var(--text)' }}>Score Overview</p>
            <div style={{ height: 220 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={[...deptEmployees].sort((a,b)=>b.total_score-a.total_score).slice(0,12)}
                  margin={{ bottom:45, left:0, right:10, top:5 }}>
                  <XAxis dataKey="employee_name" tick={{ fill:'var(--text-muted)', fontSize:11 }}
                    tickFormatter={n=>n.split(' ')[0]} angle={-35} textAnchor="end" interval={0}/>
                  <YAxis domain={[0,100]} tick={{ fill:'var(--text-muted)', fontSize:11 }}/>
                  <ReferenceLine y={90} stroke="#10B98145" strokeDasharray="4 3"/>
                  <ReferenceLine y={60} stroke="#F59E0B45" strokeDasharray="4 3"/>
                  <Tooltip
                    contentStyle={{ background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:10, fontSize:13 }}
                    cursor={{ fill:'var(--bg-hover)' }}
                    formatter={(v,n,p)=>[fmtScore(v),p.payload.employee_name]} labelFormatter={()=>''}/>
                  <Bar dataKey="total_score" radius={[4,4,0,0]} maxBarSize={30}>
                    {[...deptEmployees].sort((a,b)=>b.total_score-a.total_score).slice(0,12)
                      .map((e,i)=><Cell key={i} fill={TIER_COLOR[e.tier?.grade]??'#6366F1'}/>)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Employee table — FIXED: bounded height + internal scroll so the
          sticky header has an actual scrolling ancestor to attach to. */}
      <div className="card overflow-hidden flex flex-col" style={{ maxHeight: '80vh' }}>
        <div className="flex items-center justify-between px-5 py-3.5 border-b flex-wrap gap-3"
          style={{ borderColor:'var(--border)' }}>
          <div className="flex items-center gap-3 flex-wrap">
            <p className="font-semibold text-sm" style={{ color:'var(--text)' }}>
              Employees
              <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full"
                style={{ background:'var(--bg-hover)', color:'var(--text-muted)' }}>
                {filtered.length}
              </span>
            </p>
            <DeptDropdown value={dept} onChange={v => { setDept(v); setFilter('ALL') }}/>
            <div className="flex items-center gap-1">
              <SortBtn val="name_asc"   label="A→Z"/>
              <SortBtn val="name_desc"  label="Z→A"/>
              <SortBtn val="score_desc" label="Score↓"/>
              <SortBtn val="score_asc"  label="Score↑"/>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color:'var(--text-faint)' }}/>
              <input value={search} onChange={e=>setSearch(e.target.value)}
                placeholder="Search employee…" className="form-input pl-7 pr-7 w-44"/>
              {search && (
                <button onClick={()=>setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2"
                  style={{ color:'var(--text-faint)' }}><X size={12}/></button>
              )}
            </div>
            {['ALL','A','B','C'].map(t=>(
              <button key={t} onClick={()=>setFilter(t)}
                className={`btn text-xs py-1 px-3 ${filter===t?'btn-primary':'btn-secondary'}`}>
                {t==='ALL'?'All':`Tier ${t}`}
              </button>
            ))}
          </div>
        </div>

        {loading && (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <div className="w-10 h-10 rounded-full animate-spin"
              style={{ border:'3px solid var(--border)', borderTopColor:'#6366F1' }}/>
            <p className="font-medium text-sm" style={{ color:'var(--text)' }}>
              Fetching {monthName(month)} {year}…
            </p>
            <p className="text-xs" style={{ color:'var(--text-faint)' }}>First load: 2–3 min · Cached: instant</p>
          </div>
        )}

        {!loading && employees.length === 0 && !error && (
          <div className="text-center py-14">
            <p className="text-3xl mb-3">📭</p>
            <p className="font-semibold" style={{ color:'var(--text)' }}>No data for {monthName(month)} {year}</p>
          </div>
        )}

        {/* FIXED: overflow-auto (both axes) + flex-1 = actual scrolling
            ancestor for the sticky <thead> row to attach to. */}
        {!loading && filtered.length > 0 && (
          <div className="overflow-auto flex-1">
            <table className="w-full">
              <thead>
                <tr style={{ background:'var(--bg)', borderBottom:'1px solid var(--border)',
                             position: 'sticky', top: 0, zIndex: 10 }}>
                  {['#','EMPLOYEE','TIER',
                    ...visibleKPIs.map(k=>k.name.split(' ').slice(0,2).join(' ').toUpperCase()),
                    'SCORE',''].map((h,i)=>(
                    <th key={i} className={`px-4 py-2.5 text-xs font-semibold ${i>=5?'text-right':'text-left'}`}
                      style={{ color:'var(--text-faint)', background:'var(--bg)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((emp,i)=>(
                  <EmpRow key={emp.admin_id} emp={emp} rank={i+1} visibleKPIs={visibleKPIs}
                    onClickName={e=>navigate(`/employee/${e.admin_id}?month=${month}&year=${year}`)}
                    onClickFormula={e=>setFEmp(e)}/>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && deptEmployees.length > 0 && filtered.length === 0 && (
          <div className="text-center py-10">
            <p style={{ color:'var(--text-muted)' }}>No employees match your filters.</p>
          </div>
        )}

        {dept !== 'All' && (
          <div className="px-5 py-3 border-t text-xs" style={{ borderColor:'var(--border)', color:'var(--text-faint)' }}>
            Showing {dept === 'Conversion' ? 'all KPIs' : 'attendance KPIs only'} for {dept} department.
          </div>
        )}
      </div>

      <AnimatePresence>
        {showKPI && <KPIWeightManager onClose={()=>{setShowKPI(false);fetchData(month,year)}}/>}
        {formulaEmp && <FormulaModal emp={formulaEmp} onClose={()=>setFEmp(null)}/>}
      </AnimatePresence>
    </div>
  )
}

// import { useEffect, useState, useRef } from 'react'
// import { useNavigate } from 'react-router-dom'
// import { motion, AnimatePresence } from 'framer-motion'
// import {
//   BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer,
//   PieChart, Pie, ReferenceLine,
// } from 'recharts'
// import { useStore } from '../store/appStore'
// import { MONTHS, YEARS, fmtScore, monthName } from '../utils/formatters'
// import KPIWeightManager from '../components/KPIWeightManager'
// import StatCard from '../components/cards/StatCard'
// import {
//   Search, Settings, RefreshCw, TrendingUp, Users, Trophy,
//   AlertTriangle, X, Info, ChevronDown, ChevronUp,
//   ArrowUpDown, ArrowUp, ArrowDown, Building2,
// } from 'lucide-react'
// import toast from 'react-hot-toast'

// const TIER_COLOR = { A: '#10B981', B: '#F59E0B', C: '#EF4444' }

// const DEPT_MAP = {
//   Conversion: [
//     17, 19, 107, 148, 172, 303, 304, 315, 322, 323, 331, 336, 338,
//     344, 346, 350, 351, 352, 359, 370, 377, 389, 397, 404, 415, 423,
//     453, 454, 486, 489, 491, 493, 495, 507, 542, 544, 582, 856, 861,
//     865, 868, 879, 908, 909,
//   ],
//   IT:            [],
//   Communication: [],
// }

// const DEPT_KPI_KEYS = {
//   All:           null,
//   Conversion:    ['post_conversion', 'delayed_conversion', 'missing_status',
//                   'leaves', 'late_comings', 'early_leavings', 'independence'],
//   IT:            ['leaves', 'late_comings', 'early_leavings', 'independence'],
//   Email:         ['leaves', 'late_comings', 'early_leavings', 'independence'],
//   Account:       ['leaves', 'late_comings', 'early_leavings', 'independence'],
//   HR:            ['leaves', 'late_comings', 'early_leavings', 'independence'],
//   Communication: ['leaves', 'late_comings', 'early_leavings', 'independence'],
//   RND:           ['leaves', 'late_comings', 'early_leavings', 'independence'],
// }

// const DEPT_OPTS = [
//   { key: 'All',          label: 'All Departments', icon: '🏢' },
//   { key: 'Conversion',   label: 'Conversion',       icon: '🔄' },
//   { key: 'IT',           label: 'IT Department',    icon: '💻' },
//   { key: 'Email',        label: 'Email Team',        icon: '📧' },
//   { key: 'Account',      label: 'Accounts',          icon: '💰' },
//   { key: 'HR',           label: 'Human Resources',   icon: '👥' },
//   { key: 'Communication',label: 'Communication',     icon: '📞' },
//   { key: 'RND',          label: 'R&D',               icon: '🔬' },
// ]

// function DeptDropdown({ value, onChange }) {
//   const [open, setOpen] = useState(false)
//   const ref = useRef(null)
//   const cur = DEPT_OPTS.find(o => o.key === value) || DEPT_OPTS[0]

//   useEffect(() => {
//     const fn = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
//     document.addEventListener('mousedown', fn)
//     return () => document.removeEventListener('mousedown', fn)
//   }, [])

//   return (
//     <div className="relative" ref={ref}>
//       <button onClick={() => setOpen(o => !o)}
//         className="btn btn-secondary flex items-center gap-2"
//         style={{ minWidth: 165 }}>
//         <span>{cur.icon}</span>
//         <span className="flex-1 text-left text-sm">{cur.label}</span>
//         <ChevronDown size={12} style={{ opacity: 0.5 }}/>
//       </button>
//       <AnimatePresence>
//         {open && (
//           <motion.div
//             initial={{ opacity: 0, y: 4, scale: 0.97 }}
//             animate={{ opacity: 1, y: 0, scale: 1 }}
//             exit={{ opacity: 0, y: 4, scale: 0.97 }}
//             transition={{ duration: 0.12 }}
//             className="absolute left-0 top-full mt-1 rounded-xl border z-30 overflow-hidden"
//             style={{
//               background: 'var(--bg-card)',
//               borderColor: 'var(--border)',
//               minWidth: 185,
//               boxShadow: '0 8px 24px rgba(0,0,0,0.10)',
//             }}>
//             {DEPT_OPTS.map(o => (
//               <button key={o.key}
//                 onClick={() => { onChange(o.key); setOpen(false) }}
//                 className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-left transition-colors"
//                 style={{
//                   background: value === o.key ? 'var(--primary-soft)' : 'transparent',
//                   color: value === o.key ? '#6366F1' : 'var(--text)',
//                   fontWeight: value === o.key ? 600 : 400,
//                 }}>
//                 <span style={{ fontSize: 14 }}>{o.icon}</span>
//                 {o.label}
//               </button>
//             ))}
//           </motion.div>
//         )}
//       </AnimatePresence>
//     </div>
//   )
// }

// function FormulaModal({ emp, onClose }) {
//   if (!emp) return null
//   const kpis = Object.entries(emp.kpi_breakdown || {})
//   const tc = TIER_COLOR[emp.tier?.grade] ?? '#6366F1'
//   return (
//     <motion.div className="fixed inset-0 z-50 flex items-center justify-center"
//       initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
//       <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.45)' }} onClick={onClose}/>
//       <motion.div className="relative card p-6 w-[500px] max-h-[85vh] overflow-y-auto"
//         initial={{ scale: 0.92, y: 12 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.92, y: 12 }}
//         style={{ boxShadow: '0 24px 80px rgba(0,0,0,0.20)', background: 'var(--bg-card)' }}>
//         <div className="flex items-center justify-between mb-5">
//           <div>
//             <p className="font-bold text-base" style={{ color: 'var(--text)' }}>Score Formula</p>
//             <p className="text-sm" style={{ color: 'var(--text-muted)' }}>{emp.employee_name}</p>
//           </div>
//           <button onClick={onClose} className="p-1.5 rounded-lg"
//             style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)' }}>
//             <X size={16}/>
//           </button>
//         </div>
//         <div className="space-y-1 mb-5">
//           <div className="grid grid-cols-4 gap-2 pb-2 border-b text-[10px] font-bold uppercase tracking-wider"
//             style={{ color: 'var(--text-faint)', borderColor: 'var(--border)' }}>
//             <span className="col-span-2">KPI</span>
//             <span className="text-center">Ratio</span>
//             <span className="text-right">Score</span>
//           </div>
//           {kpis.map(([key, kpi]) => {
//             const r = kpi.success_ratio ?? 0
//             const s = kpi.score ?? 0
//             const has = kpi.success_ratio !== null
//             return (
//               <div key={key} className="grid grid-cols-4 gap-2 py-2 rounded-lg px-2"
//                 style={{ background: has ? 'var(--bg-hover)' : 'transparent' }}>
//                 <div className="col-span-2">
//                   <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>{kpi.name}</p>
//                   <p className="text-xs" style={{ color: 'var(--text-faint)' }}>
//                     {kpi.weight?.toFixed(1)}% weight · {kpi.numerator}/{kpi.denominator}
//                   </p>
//                 </div>
//                 <div className="flex flex-col items-center justify-center">
//                   {has ? (
//                     <>
//                       <span className="text-sm font-medium" style={{ color: '#6366F1' }}>{r.toFixed(1)}%</span>
//                       <div className="w-full h-1 rounded-full mt-1" style={{ background: 'var(--border)' }}>
//                         <div className="h-full rounded-full" style={{ width: `${Math.min(r,100)}%`, background: '#6366F1' }}/>
//                       </div>
//                     </>
//                   ) : <span className="text-xs" style={{ color: 'var(--text-faint)' }}>N/A</span>}
//                 </div>
//                 <div className="flex items-center justify-end">
//                   <span className="text-sm font-semibold tabular-nums"
//                     style={{ color: has ? tc : 'var(--text-faint)' }}>
//                     {has ? s.toFixed(2) : '—'}
//                   </span>
//                 </div>
//               </div>
//             )
//           })}
//         </div>
//         <div className="border-t pt-4 flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
//           <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Total Score</p>
//           <p className="text-2xl font-light tabular-nums" style={{ color: tc }}>{fmtScore(emp.total_score)}</p>
//         </div>
//         <div className="mt-3 p-3 rounded-lg text-xs" style={{ background: 'var(--bg-hover)', color: 'var(--text-faint)' }}>
//           Total = Σ (KPI Ratio × Weight / 100) — Max 100 pts
//         </div>
//       </motion.div>
//     </motion.div>
//   )
// }

// function KPIDrillDown({ kpiKey, kpi, emp }) {
//   const orders = kpi?.orders || []
//   const o = orders[0]

//   if (!orders.length) return (
//     <div className="px-6 py-3 text-xs italic" style={{ color: 'var(--text-faint)' }}>
//       No details available for this month.
//     </div>
//   )

//   if (kpiKey === 'missing_status') return (
//     <div className="px-6 py-3 flex gap-8 text-sm">
//       <span style={{ color: 'var(--text-muted)' }}>
//         Working days: <b style={{ color: 'var(--text)' }}>{o?.TotalActiveDays ?? o?.working_days ?? '—'}</b>
//       </span>
//       <span style={{ color: '#10B981' }}>Updated: <b>{o?.DaysWithUpdate ?? '—'}</b></span>
//       <span style={{ color: '#EF4444' }}>
//         Missed: <b>{o?.MissedDays ?? ((o?.TotalActiveDays ?? 0) - (o?.DaysWithUpdate ?? 0))}</b>
//       </span>
//     </div>
//   )

//   if (kpiKey === 'leaves') {
//     const dates = o?.leave_dates || []
//     return (
//       <div className="px-6 py-3">
//         <div className="flex gap-8 text-sm mb-3">
//           <span style={{ color: 'var(--text-muted)' }}>
//             Working days: <b style={{ color: 'var(--text)' }}>{o?.working_days ?? '—'}</b>
//           </span>
//           <span style={{ color: '#10B981' }}>Present: <b>{o?.present_days ?? '—'}</b></span>
//           <span style={{ color: '#EF4444' }}>Leaves taken: <b>{o?.leave_days ?? '—'}</b></span>
//         </div>
//         {dates.length > 0 && (
//           <div>
//             <p className="text-[10px] font-bold uppercase tracking-wider mb-1.5"
//               style={{ color: 'var(--text-faint)' }}>Leave Dates</p>
//             <div className="flex flex-wrap gap-1.5">
//               {dates.map((d, i) => (
//                 <span key={i} className="text-xs px-2 py-0.5 rounded-lg font-medium"
//                   style={{ background: '#FEE2E2', color: '#DC2626' }}>{d}</span>
//               ))}
//             </div>
//           </div>
//         )}
//         {dates.length === 0 && (
//           <p className="text-xs" style={{ color: '#10B981' }}>✓ No leaves taken this month</p>
//         )}
//       </div>
//     )
//   }

//   if (kpiKey === 'late_comings') {
//     const entries = o?.late_entries || []
//     const toIST = (s) => {
//       if (!s) return '—'
//       try {
//         return new Date(s.replace(' UTC', 'Z'))
//           .toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' })
//       } catch { return s }
//     }
//     // DISPLAY-ONLY grace label: shift_start + 15 minutes, formatted the
//     // same way as every other time on this card. This is NOT the real
//     // backend grace threshold (which is 20 minutes) — it's purely a
//     // simplified figure shown to employees, per explicit request.
//     //
//     // Reads o.shift_start (the person's modal/typical shift start,
//     // PRESENT FOR EVERY EMPLOYEE regardless of late history) instead of
//     // entries[0].shift_start (only exists for people who have at least
//     // one late arrival — which was causing blank grace for everyone
//     // with zero late days). o.shift_start is a plain "HH:MM" 24-hour
//     // string (e.g. "10:30"), NOT a UTC datetime string, so it's parsed
//     // differently here than the per-row punch times elsewhere on this card.
//     const graceLabel = (() => {
//       const shiftStartHHMM = o?.shift_start
//       if (!shiftStartHHMM || shiftStartHHMM === '--') return '—'
//       const match = /^(\d{1,2}):(\d{2})$/.exec(shiftStartHHMM)
//       if (!match) return '—'
//       const hours = parseInt(match[1], 10)
//       const mins  = parseInt(match[2], 10)
//       if (Number.isNaN(hours) || Number.isNaN(mins)) return '—'
//       const totalMins = (hours * 60 + mins + 15) % (24 * 60)
//       const graceH = Math.floor(totalMins / 60)
//       const graceM = totalMins % 60
//       const period = graceH >= 12 ? 'pm' : 'am'
//       const displayH = graceH % 12 === 0 ? 12 : graceH % 12
//       return `${String(displayH).padStart(2,'0')}:${String(graceM).padStart(2,'0')} ${period}`
//     })()
//     return (
//       <div className="px-6 py-3">
//         <div className="flex gap-8 text-sm mb-3">
//           <span style={{ color: 'var(--text-muted)' }}>
//             Working days: <b style={{ color: 'var(--text)' }}>{o?.working_days ?? '—'}</b>
//           </span>
//           <span style={{ color: '#10B981' }}>On-time: <b>{o?.on_time_days ?? '—'}</b></span>
//           <span style={{ color: '#EF4444' }}>Late arrivals: <b>{o?.late_days ?? '—'}</b></span>
//           <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>Grace: {graceLabel} IST</span>
//         </div>
//         {entries.length > 0 ? (
//           <table className="w-full text-xs">
//             <thead>
//               <tr style={{ borderBottom: '1px solid var(--border)' }}>
//                 {['Date', 'Shift Start (IST)', 'Actual Punch In (IST)', 'Delay'].map((h, i) => (
//                   <th key={i} className="text-left py-1.5 pr-4 font-semibold"
//                     style={{ color: 'var(--text-faint)' }}>{h}</th>
//                 ))}
//               </tr>
//             </thead>
//             <tbody>
//               {entries.map((e, i) => {
//                 let delay = '—'
//                 try {
//                   const mins = Math.round(
//                     (new Date(e.punch_in?.replace(' UTC','Z')) -
//                      new Date(e.shift_start?.replace(' UTC','Z'))) / 60000
//                   )
//                   if (mins > 0) delay = `+${mins} min`
//                 } catch {}
//                 return (
//                   <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
//                     <td className="py-1.5 pr-4 font-medium" style={{ color: 'var(--text)' }}>{e.date}</td>
//                     <td className="py-1.5 pr-4 tabular-nums" style={{ color: 'var(--text-muted)' }}>
//                       {toIST(e.shift_start)}
//                     </td>
//                     <td className="py-1.5 pr-4 tabular-nums font-medium" style={{ color: '#EF4444' }}>
//                       {toIST(e.punch_in)}
//                     </td>
//                     <td className="py-1.5 font-bold" style={{ color: '#EF4444' }}>{delay}</td>
//                   </tr>
//                 )
//               })}
//             </tbody>
//           </table>
//         ) : (
//           <p className="text-xs" style={{ color: '#10B981' }}>✓ No late arrivals this month</p>
//         )}
//       </div>
//     )
//   }

//   if (kpiKey === 'early_leavings') {
//     const entries = o?.early_entries || []
//     return (
//       <div className="px-6 py-3">
//         <div className="flex gap-8 text-sm mb-3">
//           <span style={{ color: 'var(--text-muted)' }}>
//             Working days: <b style={{ color: 'var(--text)' }}>{o?.working_days ?? '—'}</b>
//           </span>
//           <span style={{ color: '#10B981' }}>Full days: <b>{o?.full_days ?? '—'}</b></span>
//           <span style={{ color: '#EF4444' }}>Early exits: <b>{o?.early_days ?? '—'}</b></span>
//           <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>Expected: 8.5h</span>
//         </div>
//         {entries.length > 0 ? (
//           <table className="w-full text-xs">
//             <thead>
//               <tr style={{ borderBottom: '1px solid var(--border)' }}>
//                 {['Date', 'Expected Hours', 'Actual Hours', 'Shortfall'].map((h, i) => (
//                   <th key={i} className="text-left py-1.5 pr-4 font-semibold"
//                     style={{ color: 'var(--text-faint)' }}>{h}</th>
//                 ))}
//               </tr>
//             </thead>
//             <tbody>
//               {entries.map((e, i) => (
//                 <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
//                   <td className="py-1.5 pr-4 font-medium" style={{ color: 'var(--text)' }}>{e.date}</td>
//                   <td className="py-1.5 pr-4 tabular-nums" style={{ color: 'var(--text-muted)' }}>
//                     {e.expected_hours}h
//                   </td>
//                   <td className="py-1.5 pr-4 tabular-nums font-medium" style={{ color: '#EF4444' }}>
//                     {e.actual_hours}h
//                   </td>
//                   <td className="py-1.5 font-bold" style={{ color: '#EF4444' }}>
//                     -{e.shortfall_hrs}h
//                   </td>
//                 </tr>
//               ))}
//             </tbody>
//           </table>
//         ) : (
//           <p className="text-xs" style={{ color: '#10B981' }}>✓ No early exits this month</p>
//         )}
//       </div>
//     )
//   }

//   if (kpiKey === 'independence') return (
//     <div className="px-6 py-3 flex gap-8 text-sm">
//       <span style={{ color: 'var(--text-muted)' }}>
//         Rating: <b style={{ color: '#6366F1' }}>{o?.rating ?? 'Not rated'}</b>
//       </span>
//       <span style={{ color: 'var(--text-muted)' }}>
//         Score: <b style={{ color: '#6366F1' }}>{o?.score_pct ?? '—'}%</b>
//       </span>
//       {o?.rated_by && (
//         <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>Rated by: {o.rated_by}</span>
//       )}
//     </div>
//   )

//   const isDelayed = kpiKey === 'delayed_conversion'
//   return (
//     <div className="px-6 py-3">
//       <p className="text-xs font-bold mb-2" style={{ color: 'var(--text-faint)' }}>
//         {isDelayed ? 'DELIVERY DETAILS' : 'FILES WITH ISSUES'}&nbsp;
//         <span className="font-normal">
//           ({orders.filter(o => isDelayed ? o.status === 'Delayed' : o.issue === 'Issue').length} problem
//           {' '}/ {orders.length} total)
//         </span>
//       </p>
//       <div className="overflow-x-auto">
//         <table className="w-full text-xs">
//           <thead>
//             <tr style={{ borderBottom: '1px solid var(--border)' }}>
//               {['Order #', 'Company', 'Completed', isDelayed ? 'ETA' : null, 'Status']
//                 .filter(Boolean).map((h, i) => (
//                 <th key={i} className="text-left py-1.5 pr-4 font-semibold"
//                   style={{ color: 'var(--text-faint)' }}>{h}</th>
//               ))}
//             </tr>
//           </thead>
//           <tbody>
//             {orders.slice(0, 12).map((o, i) => {
//               const bad = isDelayed ? o.status === 'Delayed' : o.issue === 'Issue'
//               return (
//                 <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
//                   <td className="py-1.5 pr-4 font-mono" style={{ color: 'var(--text-muted)' }}>
//                     {o.order_number || o.order_id}
//                   </td>
//                   <td className="py-1.5 pr-4 max-w-[180px] truncate" style={{ color: 'var(--text)' }}>
//                     {o.company}
//                   </td>
//                   <td className="py-1.5 pr-4 tabular-nums" style={{ color: 'var(--text-muted)' }}>
//                     {o.completed}
//                   </td>
//                   {isDelayed && (
//                     <td className="py-1.5 pr-4 tabular-nums" style={{ color: 'var(--text-muted)' }}>
//                       {o.eta || '—'}
//                     </td>
//                   )}
//                   <td className="py-1.5">
//                     <span className="px-1.5 py-0.5 rounded text-[10px] font-bold"
//                       style={{ background: bad ? '#FEE2E2' : '#DCFCE7', color: bad ? '#DC2626' : '#15803D' }}>
//                       {isDelayed ? (o.status || 'No ETA') : (o.issue || 'Clean')}
//                     </span>
//                   </td>
//                 </tr>
//               )
//             })}
//           </tbody>
//         </table>
//         {orders.length > 12 && (
//           <p className="text-xs mt-1" style={{ color: 'var(--text-faint)' }}>+{orders.length - 12} more</p>
//         )}
//       </div>
//     </div>
//   )
// }

// function EmpRow({ emp, rank, visibleKPIs, onClickName, onClickFormula }) {
//   const [drill, setDrill] = useState(null)
//   const tc = TIER_COLOR[emp.tier?.grade] ?? '#6366F1'
//   const toggle = (k) => setDrill(drill === k ? null : k)

//   return (
//     <>
//       <tr className="border-b" style={{ borderColor: 'var(--border)' }}
//         onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
//         onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
//         <td className="px-4 py-3 text-xs font-mono" style={{ color: 'var(--text-faint)' }}>{rank}</td>
//         <td className="px-4 py-3">
//           <button onClick={() => onClickName(emp)} className="flex items-center gap-2.5 group text-left">
//             <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
//               style={{ background: tc }}>{emp.employee_name?.[0]}</div>
//             <span className="font-medium text-sm group-hover:underline decoration-dotted"
//               style={{ color: 'var(--text)' }}>{emp.employee_name}</span>
//           </button>
//         </td>
//         <td className="px-4 py-3">
//           <span className="text-xs font-bold px-2 py-0.5 rounded-full"
//             style={{ background: `${tc}18`, color: tc }}>
//             Tier {emp.tier?.grade}
//           </span>
//         </td>
//         {visibleKPIs.map(k => {
//           const kd       = emp.kpi_breakdown?.[k.key]
//           const success  = kd?.success_ratio ?? null
//           const failPct  = success !== null ? +(100 - success).toFixed(1) : null
//           const failCount= kd ? (kd.denominator ?? 0) - (kd.numerator ?? 0) : 0
//           const denom    = kd?.denominator ?? 0
//           const isOpen   = drill === k.key
//           const barColor = failPct === null ? 'var(--border)'
//             : failPct <= 5  ? '#10B981'
//             : failPct <= 20 ? '#F59E0B'
//             : '#EF4444'
//           return (
//             <td key={k.key} className="px-4 py-3">
//               <div className="flex items-center gap-1.5">
//                 <div className="flex-1">
//                   <div className="flex items-center gap-1.5">
//                     <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
//                       <div className="h-full rounded-full transition-all"
//                         style={{ width: `${Math.min(failPct ?? 0, 100)}%`, background: barColor }}/>
//                     </div>
//                     <span className="text-xs tabular-nums w-10 text-right font-medium"
//                       style={{ color: barColor }}>
//                       {failPct !== null ? `${failPct.toFixed(1)}%` : '—'}
//                     </span>
//                   </div>
//                   {denom > 0 && (
//                     <p className="text-[10px] mt-0.5 tabular-nums" style={{ color: 'var(--text-faint)' }}>
//                       {failCount} / {denom}
//                     </p>
//                   )}
//                 </div>
//                 {kd && kd.denominator > 0 && (
//                   <button onClick={() => toggle(k.key)} title={`View ${k.name} details`}
//                     className="p-0.5 rounded transition-colors shrink-0"
//                     style={{ background: isOpen ? '#EEF2FF' : 'var(--bg-hover)', color: isOpen ? '#6366F1' : 'var(--text-faint)' }}>
//                     {isOpen ? <ChevronUp size={12}/> : <ChevronDown size={12}/>}
//                   </button>
//                 )}
//               </div>
//             </td>
//           )
//         })}
//         <td className="px-4 py-3 text-right">
//           <span className="text-xl font-light tabular-nums" style={{ color: tc }}>{fmtScore(emp.total_score)}</span>
//         </td>
//         <td className="px-3 py-3">
//           <button onClick={() => onClickFormula(emp)} title="Score formula"
//             className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border transition-colors"
//             style={{ background: 'var(--bg-hover)', color: 'var(--text-faint)', borderColor: 'var(--border)' }}
//             onMouseEnter={e => { e.currentTarget.style.background='#EEF2FF'; e.currentTarget.style.color='#6366F1' }}
//             onMouseLeave={e => { e.currentTarget.style.background='var(--bg-hover)'; e.currentTarget.style.color='var(--text-faint)' }}>
//             i
//           </button>
//         </td>
//       </tr>
//       {drill && (
//         <tr style={{ borderBottom: '1px solid var(--border)' }}>
//           <td colSpan={99} style={{ background: 'var(--bg)', padding: 0 }}>
//             <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
//               exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.18 }}>
//               <KPIDrillDown kpiKey={drill} kpi={emp.kpi_breakdown?.[drill]} emp={emp}/>
//             </motion.div>
//           </td>
//         </tr>
//       )}
//     </>
//   )
// }

// export default function Dashboard() {
//   const { setEmployees, setKPIs, kpis, employees } = useStore()
//   const navigate = useNavigate()
//   const { selectedMonth: month, selectedYear: year,
//         setSelectedMonth: setMonth, setSelectedYear: setYear } = useStore()
//   const [loading, setLoading] = useState(false)
//   const [error, setError]     = useState(null)
//   const [filter, setFilter]   = useState('ALL')
//   const [search, setSearch]   = useState('')
//   const [dept,   setDept]     = useState('All')
//   const [showKPI, setShowKPI] = useState(false)
//   const [formulaEmp, setFEmp] = useState(null)
//   const [sortBy, setSortBy]   = useState('name_asc')
//   const reqId = useRef(0)

//   const fetchData = async (m, y) => {
//     const id = ++reqId.current
//     setLoading(true); setError(null)
//     try {
//       const meRes = await fetch('/api/me', { credentials: 'include' })
//       if (!meRes.ok) { navigate('/login'); return }
//       const [scRes, kpRes] = await Promise.all([
//         fetch(`/api/scores?month=${m}&year=${y}`, { credentials: 'include' }),
//         fetch('/api/kpis', { credentials: 'include' }),
//       ])
//       if (id !== reqId.current) return
//       if (!scRes.ok) throw new Error(`HTTP ${scRes.status}`)
//       const scData = await scRes.json()
//       const kpData = await kpRes.json()
//       setEmployees(scData.employees ?? [])
//       setKPIs(kpData.kpis ?? [])
//       if (!(scData.employees ?? []).length) setError(`No data for ${monthName(m)} ${y}.`)
//     } catch (err) {
//       if (id !== reqId.current) return
//       setError(err.message); toast.error(`Load failed: ${err.message}`)
//     } finally { if (id === reqId.current) setLoading(false) }
//   }
//   useEffect(() => { fetchData(month, year) }, [month, year])

//   const deptEmployees = employees.filter(emp => {
//     if (dept === 'All') return true
//     if (dept === 'Conversion') return !!emp.is_conversion
//     const empDept = (emp.department || '').trim()
//     return empDept === dept
//   })

//   const kpiKeyFilter = DEPT_KPI_KEYS[dept]
//   const visibleKPIs  = kpis.filter(k =>
//     k.is_active && (!kpiKeyFilter || kpiKeyFilter.includes(k.key))
//   )

//   const applySort = (list) => {
//     const arr = [...list]
//     if (sortBy === 'name_asc')   return arr.sort((a,b)=>(a.employee_name||'').localeCompare(b.employee_name||''))
//     if (sortBy === 'name_desc')  return arr.sort((a,b)=>(b.employee_name||'').localeCompare(a.employee_name||''))
//     if (sortBy === 'score_desc') return arr.sort((a,b)=>b.total_score-a.total_score)
//     if (sortBy === 'score_asc')  return arr.sort((a,b)=>a.total_score-b.total_score)
//     return arr
//   }

//   const filtered = applySort(
//     deptEmployees
//       .filter(e => filter === 'ALL' || e.tier?.grade === filter)
//       .filter(e => !search || (e.employee_name||'').toLowerCase().includes(search.toLowerCase()))
//   )

//   const stats = {
//     total: deptEmployees.length,
//     A: deptEmployees.filter(e=>e.tier?.grade==='A').length,
//     B: deptEmployees.filter(e=>e.tier?.grade==='B').length,
//     C: deptEmployees.filter(e=>e.tier?.grade==='C').length,
//     avg: deptEmployees.length ? deptEmployees.reduce((s,e)=>s+(e.total_score||0),0)/deptEmployees.length : 0,
//   }

//   const donutData = ['A','B','C']
//     .map(g=>({name:`Tier ${g}`, value:stats[g], fill:TIER_COLOR[g]}))
//     .filter(d=>d.value>0)

//   const SortBtn = ({ val, label }) => (
//     <button onClick={() => setSortBy(val)}
//       className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg transition-colors"
//       style={{
//         background: sortBy===val?'var(--primary-soft)':'var(--bg-hover)',
//         color: sortBy===val?'#6366F1':'var(--text-muted)',
//         fontWeight: sortBy===val?600:400,
//       }}>
//       {sortBy===val && sortBy.includes('desc') ? <ArrowDown size={11}/> :
//        sortBy===val && sortBy.includes('asc') && sortBy!=='name_asc' ? <ArrowUp size={11}/> :
//        <ArrowUpDown size={11}/>}
//       {label}
//     </button>
//   )

//   return (
//     <div className="space-y-5">
//       <div className="flex items-center justify-between flex-wrap gap-3">
//         <div className="flex items-center gap-2 flex-wrap">
//           <select value={month} onChange={e=>setMonth(+e.target.value)} className="form-input">
//             {MONTHS.map(m=><option key={m.value} value={m.value}>{m.full}</option>)}
//           </select>
//           <select value={year} onChange={e=>setYear(+e.target.value)} className="form-input">
//             {YEARS.map(y=><option key={y} value={y}>{y}</option>)}
//           </select>
//           <button onClick={()=>fetchData(month,year)} className="btn btn-secondary" disabled={loading}>
//             <RefreshCw size={13} className={loading?'animate-spin':''}/>{loading?'Loading…':'Refresh'}
//           </button>
//         </div>
//         <button onClick={()=>setShowKPI(true)} className="btn btn-secondary">
//           <Settings size={13}/> Configure KPIs
//         </button>
//       </div>

//       {error && !loading && (
//         <div className="flex items-start gap-3 p-4 rounded-xl border"
//           style={{ background:'rgba(245,158,11,0.06)', borderColor:'rgba(245,158,11,0.3)' }}>
//           <Info size={16} className="shrink-0 mt-0.5" style={{ color:'#D97706' }}/>
//           <p className="text-sm" style={{ color:'var(--text)' }}>{error}</p>
//         </div>
//       )}

//       <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
//         <StatCard label="Active Employees" value={stats.total} sub={`${monthName(month)} ${year}`} color="indigo" icon={Users}/>
//         <StatCard label="High Performers"  value={stats.A}     sub="Tier A ≥ 90"  color="green"  icon={Trophy}/>
//         <StatCard label="Needs Attention"  value={stats.C}     sub="Tier C < 60"  color="red"    icon={AlertTriangle}/>
//         <StatCard label="Team Avg Score"   value={fmtScore(stats.avg)} sub="out of 100" color="amber" icon={TrendingUp}/>
//       </div>

//       {deptEmployees.length > 0 && (
//         <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
//           <div className="card p-5">
//             <p className="font-semibold text-sm mb-1" style={{ color:'var(--text)' }}>Tier Distribution</p>
//             <div style={{ height: 170 }}>
//               <ResponsiveContainer width="100%" height="100%">
//                 <PieChart>
//                   <Pie data={donutData} cx="50%" cy="50%" innerRadius={45} outerRadius={72} paddingAngle={3} dataKey="value">
//                     {donutData.map((d,i)=><Cell key={i} fill={d.fill}/>)}
//                   </Pie>
//                   <Tooltip contentStyle={{ background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:10, fontSize:13 }}/>
//                 </PieChart>
//               </ResponsiveContainer>
//             </div>
//             <div className="flex justify-around mt-2">
//               {['A','B','C'].map(g=>(
//                 <div key={g} className="text-center">
//                   <p className="text-2xl font-light" style={{ color:TIER_COLOR[g] }}>{stats[g]}</p>
//                   <p className="text-xs" style={{ color:'var(--text-faint)' }}>Tier {g}</p>
//                 </div>
//               ))}
//             </div>
//           </div>
//           <div className="card p-5 lg:col-span-2">
//             <p className="font-semibold text-sm mb-1" style={{ color:'var(--text)' }}>Score Overview</p>
//             <div style={{ height: 220 }}>
//               <ResponsiveContainer width="100%" height="100%">
//                 <BarChart data={[...deptEmployees].sort((a,b)=>b.total_score-a.total_score).slice(0,12)}
//                   margin={{ bottom:45, left:0, right:10, top:5 }}>
//                   <XAxis dataKey="employee_name" tick={{ fill:'var(--text-muted)', fontSize:11 }}
//                     tickFormatter={n=>n.split(' ')[0]} angle={-35} textAnchor="end" interval={0}/>
//                   <YAxis domain={[0,100]} tick={{ fill:'var(--text-muted)', fontSize:11 }}/>
//                   <ReferenceLine y={90} stroke="#10B98145" strokeDasharray="4 3"/>
//                   <ReferenceLine y={60} stroke="#F59E0B45" strokeDasharray="4 3"/>
//                   <Tooltip
//                     contentStyle={{ background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:10, fontSize:13 }}
//                     cursor={{ fill:'var(--bg-hover)' }}
//                     formatter={(v,n,p)=>[fmtScore(v),p.payload.employee_name]} labelFormatter={()=>''}/>
//                   <Bar dataKey="total_score" radius={[4,4,0,0]} maxBarSize={30}>
//                     {[...deptEmployees].sort((a,b)=>b.total_score-a.total_score).slice(0,12)
//                       .map((e,i)=><Cell key={i} fill={TIER_COLOR[e.tier?.grade]??'#6366F1'}/>)}
//                   </Bar>
//                 </BarChart>
//               </ResponsiveContainer>
//             </div>
//           </div>
//         </div>
//       )}

//       {/* Employee table — FIXED: bounded height + internal scroll so the
//           sticky header has an actual scrolling ancestor to attach to. */}
//       <div className="card overflow-hidden flex flex-col" style={{ maxHeight: '80vh' }}>
//         <div className="flex items-center justify-between px-5 py-3.5 border-b flex-wrap gap-3"
//           style={{ borderColor:'var(--border)' }}>
//           <div className="flex items-center gap-3 flex-wrap">
//             <p className="font-semibold text-sm" style={{ color:'var(--text)' }}>
//               Employees
//               <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full"
//                 style={{ background:'var(--bg-hover)', color:'var(--text-muted)' }}>
//                 {filtered.length}
//               </span>
//             </p>
//             <DeptDropdown value={dept} onChange={v => { setDept(v); setFilter('ALL') }}/>
//             <div className="flex items-center gap-1">
//               <SortBtn val="name_asc"   label="A→Z"/>
//               <SortBtn val="name_desc"  label="Z→A"/>
//               <SortBtn val="score_desc" label="Score↓"/>
//               <SortBtn val="score_asc"  label="Score↑"/>
//             </div>
//           </div>
//           <div className="flex items-center gap-2 flex-wrap">
//             <div className="relative">
//               <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color:'var(--text-faint)' }}/>
//               <input value={search} onChange={e=>setSearch(e.target.value)}
//                 placeholder="Search employee…" className="form-input pl-7 pr-7 w-44"/>
//               {search && (
//                 <button onClick={()=>setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2"
//                   style={{ color:'var(--text-faint)' }}><X size={12}/></button>
//               )}
//             </div>
//             {['ALL','A','B','C'].map(t=>(
//               <button key={t} onClick={()=>setFilter(t)}
//                 className={`btn text-xs py-1 px-3 ${filter===t?'btn-primary':'btn-secondary'}`}>
//                 {t==='ALL'?'All':`Tier ${t}`}
//               </button>
//             ))}
//           </div>
//         </div>

//         {loading && (
//           <div className="flex flex-col items-center justify-center py-16 gap-3">
//             <div className="w-10 h-10 rounded-full animate-spin"
//               style={{ border:'3px solid var(--border)', borderTopColor:'#6366F1' }}/>
//             <p className="font-medium text-sm" style={{ color:'var(--text)' }}>
//               Fetching {monthName(month)} {year}…
//             </p>
//             <p className="text-xs" style={{ color:'var(--text-faint)' }}>First load: 2–3 min · Cached: instant</p>
//           </div>
//         )}

//         {!loading && employees.length === 0 && !error && (
//           <div className="text-center py-14">
//             <p className="text-3xl mb-3">📭</p>
//             <p className="font-semibold" style={{ color:'var(--text)' }}>No data for {monthName(month)} {year}</p>
//           </div>
//         )}

//         {/* FIXED: overflow-auto (both axes) + flex-1 = actual scrolling
//             ancestor for the sticky <thead> row to attach to. */}
//         {!loading && filtered.length > 0 && (
//           <div className="overflow-auto flex-1">
//             <table className="w-full">
//               <thead>
//                 <tr style={{ background:'var(--bg)', borderBottom:'1px solid var(--border)',
//                              position: 'sticky', top: 0, zIndex: 10 }}>
//                   {['#','EMPLOYEE','TIER',
//                     ...visibleKPIs.map(k=>k.name.split(' ').slice(0,2).join(' ').toUpperCase()),
//                     'SCORE',''].map((h,i)=>(
//                     <th key={i} className={`px-4 py-2.5 text-xs font-semibold ${i>=5?'text-right':'text-left'}`}
//                       style={{ color:'var(--text-faint)', background:'var(--bg)' }}>{h}</th>
//                   ))}
//                 </tr>
//               </thead>
//               <tbody>
//                 {filtered.map((emp,i)=>(
//                   <EmpRow key={emp.admin_id} emp={emp} rank={i+1} visibleKPIs={visibleKPIs}
//                     onClickName={e=>navigate(`/employee/${e.admin_id}?month=${month}&year=${year}`)}
//                     onClickFormula={e=>setFEmp(e)}/>
//                 ))}
//               </tbody>
//             </table>
//           </div>
//         )}

//         {!loading && deptEmployees.length > 0 && filtered.length === 0 && (
//           <div className="text-center py-10">
//             <p style={{ color:'var(--text-muted)' }}>No employees match your filters.</p>
//           </div>
//         )}

//         {dept !== 'All' && (
//           <div className="px-5 py-3 border-t text-xs" style={{ borderColor:'var(--border)', color:'var(--text-faint)' }}>
//             Showing {dept === 'Conversion' ? 'all KPIs' : 'attendance KPIs only'} for {dept} department.
//           </div>
//         )}
//       </div>

//       <AnimatePresence>
//         {showKPI && <KPIWeightManager onClose={()=>{setShowKPI(false);fetchData(month,year)}}/>}
//         {formulaEmp && <FormulaModal emp={formulaEmp} onClose={()=>setFEmp(null)}/>}
//       </AnimatePresence>
//     </div>
//   )
// }

