import { useEffect, useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell,
} from 'recharts'
import { ArrowLeft, CheckCircle, XCircle, Clock } from 'lucide-react'
import { monthName, fmtScore } from '../utils/formatters'
import toast from 'react-hot-toast'

const TIER_COLOR  = { A: '#10B981', B: '#F59E0B', C: '#EF4444' }
const KPI_COLORS  = ['#6366F1','#10B981','#F59E0B','#EF4444','#8B5CF6','#06B6D4','#EC4899','#14B8A6']
const MONTH_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

function ScoreCircle({ score, tier }) {
  const c    = TIER_COLOR[tier] ?? '#6366F1'
  const r    = 52, cx = 64, cy = 64
  const circ = 2 * Math.PI * r
  const dash = circ * (Math.min(score, 100) / 100)
  return (
    <svg width={128} height={128}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--border)" strokeWidth={8}
        style={{ transform: 'rotate(-90deg)', transformOrigin: '50% 50%' }}/>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={c} strokeWidth={8}
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        style={{ transform: 'rotate(-90deg)', transformOrigin: '50% 50%', transition: 'stroke-dasharray 0.8s' }}/>
      <text x={cx} y={cy - 4} textAnchor="middle" fill={c}
        style={{ fontSize: 24, fontWeight: 300 }}>{fmtScore(score)}</text>
      <text x={cx} y={cy + 16} textAnchor="middle" fill="var(--text-faint)"
        style={{ fontSize: 11 }}>/ 100</text>
    </svg>
  )
}

export default function EmployeeDetail() {
  const { id }     = useParams()
  const [sp]       = useSearchParams()
  const navigate   = useNavigate()
  const [month, setMonth] = useState(parseInt(sp.get('month') || new Date().getMonth() + 1))
  const [year,  setYear]  = useState(parseInt(sp.get('year')  || 2026))
  const [detail,  setDetail]  = useState(null)
  const [trend,   setTrend]   = useState([])
  const [loading, setLoading] = useState(true)
  const [trendOk, setTrendOk] = useState(false)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/scores/${id}?month=${month}&year=${year}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => { setDetail(d); setLoading(false) })
      .catch(e => { toast.error(`Load failed: ${e}`); setLoading(false) })
  }, [id, month, year])

  useEffect(() => {
    fetch(`/api/scores/${id}/trend?year=${year}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => {
        setTrend((d.trend || []).map(t => ({
          m: MONTH_SHORT[t.month - 1],
          score: t.total_score,
        })))
        setTrendOk(true)
      })
      .catch(() => setTrendOk(false))
  }, [id, year])

  if (loading) return (
    <div className="flex items-center justify-center py-24">
      <div className="w-10 h-10 rounded-full animate-spin"
        style={{ border: '3px solid var(--border)', borderTopColor: '#6366F1' }}/>
    </div>
  )
  if (!detail) return (
    <div className="text-center py-20" style={{ color: 'var(--text-muted)' }}>Employee not found.</div>
  )

  const tc   = TIER_COLOR[detail.tier?.grade] ?? '#6366F1'
  const kpis = Object.entries(detail.kpi_breakdown || {})
  const barData = kpis.map(([, k], i) => ({
    name: k.name.split(' ').slice(0, 2).join(' '),
    value: +(100 - (k.success_ratio ?? 100)).toFixed(1),  // failure ratio
    fill: KPI_COLORS[i % KPI_COLORS.length],
  }))

  // Merge orders across KPIs into unified file table
  const fileMap = {}
  kpis.forEach(([key, kpi]) => {
    ;(kpi.orders || []).forEach(o => {
      const oid = o.order_id || o.OrderID
      if (!oid) return
      if (!fileMap[oid]) {
        fileMap[oid] = {
          oid,
          num:       o.order_number || o.OrderNumber || String(oid),
          company:   o.company || o.CompanyName || '—',
          completed: o.completed || o.FinalCompletionDate || '—',
          post:  null, delayed: null, missing: null,
        }
      }
      if (key === 'post_conversion') {
        fileMap[oid].post = o.issue || 'Clean'
        // Always update completed from post_conversion — it has the most accurate date logic
        if (o.completed && o.completed !== '—') fileMap[oid].completed = o.completed
      }
      if (key === 'delayed_conversion') {
        fileMap[oid].delayed = o.status || 'No ETA'
        if (o.completed && o.completed !== '—') fileMap[oid].completed = o.completed
      }
      if (key === 'missing_status' && o._is_file_entry && oid) {
        if (fileMap[oid]) {
          const activeDays = o.ActiveDays || o.active_days || 0
          fileMap[oid].missing        = `${o.DaysMissed || 0}/${activeDays}d`
          fileMap[oid].missing_missed = o.DaysMissed || 0
          fileMap[oid].missing_active = activeDays
        }
      }
    })
  })
  const files = Object.values(fileMap).sort((a, b) =>
    String(a.completed).localeCompare(String(b.completed)))

  return (
    <div className="space-y-5">
      <button onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
        <ArrowLeft size={15}/> Back
      </button>

      {/* ── Hero ──────────────────────────────────────────────────── */}
      <div className="card p-6 flex items-center gap-6 flex-wrap">
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-bold text-white"
          style={{ background: tc }}>
          {detail.employee_name?.[0]}
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text)' }}>{detail.employee_name}</h1>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            <span className="text-sm px-3 py-1 rounded-full font-bold"
              style={{ background: `${tc}18`, color: tc }}>
              Tier {detail.tier?.grade} — {detail.tier?.label}
            </span>
            <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {monthName(month)} {year}
            </span>
          </div>
        </div>
        <ScoreCircle score={detail.total_score} tier={detail.tier?.grade}/>
      </div>

      {/* ── Year trend line chart ─────────────────────────────────── */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div>
            <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>
              {year} Score Trend
            </p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Monthly performance — click a month to load its data
            </p>
          </div>
          <div className="flex gap-1">
            {[2025, 2026].map(y => (
              <button key={y} onClick={() => setYear(y)}
                className="text-xs px-3 py-1 rounded-lg transition-colors"
                style={{
                  background: year === y ? '#EEF2FF' : 'var(--bg-hover)',
                  color: year === y ? '#6366F1' : 'var(--text-muted)',
                  fontWeight: year === y ? 600 : 400,
                }}>{y}</button>
            ))}
          </div>
        </div>
        <div style={{ height: 200 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trend} margin={{ left: 0, right: 20, top: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)"/>
              <XAxis dataKey="m" tick={{ fill: 'var(--text-muted)', fontSize: 12 }}/>
              <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 12 }}/>
              <Tooltip
                contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, fontSize: 13 }}
                formatter={v => [v !== null ? `${v}` : 'No data', 'Score']}/>
              <Line type="monotone" dataKey="score" stroke={tc} strokeWidth={2.5}
                dot={{ fill: tc, r: 4, strokeWidth: 0 }} connectNulls={false}/>
            </LineChart>
          </ResponsiveContainer>
        </div>
        {/* Month pills */}
        <div className="flex gap-1 mt-3 flex-wrap">
          {MONTH_SHORT.map((m, i) => {
            const mn = i + 1
            const isActive = mn === month
            return (
              <button key={m} onClick={() => setMonth(mn)}
                className="text-xs px-2.5 py-1 rounded-lg transition-colors"
                style={{
                  background: isActive ? tc : 'var(--bg-hover)',
                  color: isActive ? '#fff' : 'var(--text-muted)',
                  fontWeight: isActive ? 600 : 400,
                }}>{m}</button>
            )
          })}
        </div>
      </div>

      {/* ── KPI bar chart + detail cards ─────────────────────────── */}
      <div className="card p-5">
        <p className="font-semibold text-sm mb-4" style={{ color: 'var(--text)' }}>
          KPI Failure Rates
          <span className="ml-2 text-xs font-normal" style={{ color: 'var(--text-muted)' }}>
            Problem areas this month — lower is better
          </span>
        </p>
        <div style={{ height: 170 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} layout="vertical" margin={{ left: 110, right: 70, top: 0, bottom: 0 }}>
              <XAxis type="number" domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                tickFormatter={v => `${v}%`}/>
              <YAxis type="category" dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} width={105}/>
              <Tooltip
                contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, fontSize: 13 }}
                formatter={(v, _, props) => [`${v}% failure rate`, props.payload.name]}/>
              <Bar dataKey="value" radius={[0, 4, 4, 0]} fillOpacity={0.85}
                label={{ position: 'right', fontSize: 12, fill: 'var(--text-muted)', formatter: v => `${v}%` }}>
                {barData.map((d, i) => <Cell key={i} fill={d.fill} fillOpacity={0.82}/>)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-5">
          {kpis.map(([key, kpi], i) => {
            const c = KPI_COLORS[i % KPI_COLORS.length]
            return (
              <div key={key} className="rounded-xl p-4 border" style={{ borderColor: 'var(--border)' }}>
                <div className="flex items-start justify-between mb-2">
                  <p className="font-semibold text-sm pr-2" style={{ color: 'var(--text)' }}>{kpi.name}</p>
                  <span className="text-lg font-light shrink-0" style={{ color: c }}>
                    {kpi.success_ratio !== null ? `${(100-kpi.success_ratio).toFixed(1)}%` : 'N/A'}
                    <span className="text-xs ml-1 font-normal" style={{ color: 'var(--text-faint)' }}>failure rate</span>
                  </span>
                </div>
                <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>{kpi.description}</p>
                <div className="h-1.5 rounded-full overflow-hidden mb-2" style={{ background: 'var(--border)' }}>
                  <div className="h-full rounded-full" style={{ width: `${100-(kpi.success_ratio ?? 100)}%`, background: c }}/>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span style={{ color: 'var(--text-muted)' }}>
                    {/* Show failure count: denominator - numerator / denominator */}
                    {kpi.denominator > 0
                      ? `${kpi.denominator - kpi.numerator} / ${kpi.denominator}`
                      : '— / —'}
                  </span>
                  <span className="px-2 py-0.5 rounded-full font-bold text-[10px]"
                    style={{ background: `${c}18`, color: c }}>
                    Weight: {kpi.weight?.toFixed(1)}%
                  </span>
                </div>
                <div className="flex items-center justify-between mt-2 pt-2 border-t text-xs"
                  style={{ borderColor: 'var(--border)' }}>
                  <span style={{ color: 'var(--text-faint)' }}>Score</span>
                  <span className="font-semibold" style={{ color: tc }}>
                    {kpi.score !== null ? kpi.score.toFixed(2) : '—'}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>


      {/* ── Attendance Detail ────────────────────────────────────── */}
      {(() => {
        const attendanceKPIs = ['missing_status','leaves','late_comings','early_leavings','independence']
        const attKpis = kpis.filter(([key]) => attendanceKPIs.includes(key))
        if (!attKpis.length) return null
        return (
          <div className="card p-5">
            <p className="font-semibold text-sm mb-4" style={{ color: 'var(--text)' }}>
              Attendance Detail
              <span className="ml-2 text-xs font-normal" style={{ color: 'var(--text-muted)' }}>
                {monthName(month)} {year}
              </span>
            </p>
            <div className="space-y-4">
              {attKpis.map(([key, kpi]) => {
                const o = kpi.orders?.[0]
                if (!o) return null
                const KPI_LABEL = {
                  missing_status: 'Status Not Updated', leaves: 'Leaves',
                  late_comings: 'Late Comings',
                  early_leavings: 'Early Leavings', independence: 'Independence'
                }
                return (
                  <div key={key} className="rounded-xl p-4 border" style={{ borderColor: 'var(--border)' }}>
                    <p className="font-semibold text-sm mb-3" style={{ color: 'var(--text)' }}>
                      {KPI_LABEL[key]}
                    </p>

                    {/* Missing Status — summary + per-file table */}
                    {key === 'missing_status' && (
                      <>
                        {/* Summary row — Option A scoring */}
                        <div className="flex gap-8 text-sm mb-4 flex-wrap">
                          <span style={{ color: 'var(--text-muted)' }}>
                            Working days: <b style={{ color: 'var(--text)' }}>{o.TotalActiveDays ?? '—'}</b>
                          </span>
                          <span style={{ color: '#10B981' }}>
                            Days updated: <b>{o.DaysWithUpdate ?? '—'}</b>
                          </span>
                          <span style={{ color: o.MissedDays > 0 ? '#EF4444' : '#10B981' }}>
                            Days missed: <b>{o.MissedDays ?? '—'}</b>
                          </span>
                        </div>

                        {/* Per-file breakdown table */}
                        {(o.file_breakdown || []).length > 0 ? (
                          <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                              <thead>
                                <tr style={{ borderBottom: '2px solid var(--border)',
                                             background: 'var(--bg)' }}>
                                  {['Order #','Company','Completed','Active From',
                                    'Active Days','Updated','Missed','Status'].map((h,i) => (
                                    <th key={i}
                                      className="text-left py-2 pr-4 font-bold tracking-wide"
                                      style={{ color: 'var(--text-faint)', fontSize: 10,
                                               textTransform: 'uppercase' }}>{h}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {o.file_breakdown.map((fb, i) => {
                                  const pct = fb.active_days > 0
                                    ? (fb.days_missed / fb.active_days) * 100 : 0
                                  const color = fb.days_missed === 0 ? '#10B981'
                                    : pct <= 30 ? '#F59E0B' : '#EF4444'
                                  const dot = fb.days_missed === 0 ? '🟢'
                                    : pct <= 30 ? '🟡' : '🔴'
                                  return (
                                    <tr key={i}
                                      style={{ borderBottom: '1px solid var(--border)' }}
                                      onMouseEnter={e=>e.currentTarget.style.background='var(--bg-hover)'}
                                      onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                                      <td className="py-2 pr-4 font-mono"
                                        style={{ color:'var(--text-muted)', fontSize:10 }}>
                                        {fb.order_number}
                                      </td>
                                      <td className="py-2 pr-4 max-w-[180px] truncate font-medium"
                                        style={{ color:'var(--text)' }}>{fb.company}</td>
                                      <td className="py-2 pr-4 tabular-nums"
                                        style={{ color:'var(--text-muted)' }}>{fb.completed}</td>
                                      <td className="py-2 pr-4 tabular-nums"
                                        style={{ color:'var(--text-muted)' }}>{fb.active_from}</td>
                                      <td className="py-2 pr-4 tabular-nums text-center font-medium"
                                        style={{ color:'var(--text)' }}>{fb.active_days}</td>
                                      <td className="py-2 pr-4 tabular-nums text-center font-bold"
                                        style={{ color:'#10B981' }}>{fb.days_updated}</td>
                                      <td className="py-2 pr-4 tabular-nums text-center font-bold"
                                        style={{ color: fb.days_missed > 0 ? '#EF4444':'#10B981' }}>
                                        {fb.days_missed}
                                      </td>
                                      <td className="py-2 tabular-nums font-bold text-xs"
                                        style={{ color, whiteSpace:'nowrap' }}>
                                        {dot} {fb.days_updated}/{fb.active_days}
                                      </td>
                                    </tr>
                                  )
                                })}
                              </tbody>
                              {/* Totals row */}
                              {(() => {
                                const totalActive  = o.file_breakdown.reduce((s,f)=>s+f.active_days,0)
                                const totalUpdated = o.file_breakdown.reduce((s,f)=>s+f.days_updated,0)
                                const totalMissed  = o.file_breakdown.reduce((s,f)=>s+f.days_missed,0)
                                return (
                                  <tfoot>
                                    <tr style={{ borderTop:'2px solid var(--border)',
                                                 background:'var(--bg-hover)' }}>
                                      <td colSpan={4} className="py-2 pr-4 font-bold text-xs"
                                        style={{ color:'var(--text)' }}>
                                        TOTAL ({o.file_breakdown.length} files)
                                      </td>
                                      <td className="py-2 pr-4 text-center font-bold tabular-nums"
                                        style={{ color:'var(--text)' }}>{totalActive}</td>
                                      <td className="py-2 pr-4 text-center font-bold tabular-nums"
                                        style={{ color:'#10B981' }}>{totalUpdated}</td>
                                      <td className="py-2 pr-4 text-center font-bold tabular-nums"
                                        style={{ color: totalMissed>0?'#EF4444':'#10B981' }}>
                                        {totalMissed}
                                      </td>
                                      <td className="py-2 font-bold text-xs"
                                        style={{ color: totalMissed>0?'#EF4444':'#10B981' }}>
                                        {totalUpdated}/{totalActive}
                                      </td>
                                    </tr>
                                  </tfoot>
                                )
                              })()}
                            </table>
                          </div>
                        ) : (
                          <p className="text-xs italic" style={{ color:'var(--text-faint)' }}>
                            No completed files this month.
                          </p>
                        )}
                      </>
                    )}

                    {/* Leaves */}
                    {key === 'leaves' && (
                      <>
                        <div className="flex gap-6 text-sm mb-3 flex-wrap">
                          <span style={{ color: 'var(--text-muted)' }}>Working days: <b style={{ color: 'var(--text)' }}>{o.working_days ?? '—'}</b></span>
                          <span style={{ color: '#10B981' }}>Present: <b>{o.present_days ?? '—'}</b></span>
                          <span style={{ color: o.leave_days > 0 ? '#EF4444' : '#10B981' }}>Leaves: <b>{o.leave_days ?? 0}</b></span>
                        </div>
                        {(o.leave_dates || []).length > 0 ? (
                          <div className="flex flex-wrap gap-1.5">
                            {o.leave_dates.map((d, i) => (
                              <span key={i} className="text-xs px-2 py-0.5 rounded-lg font-medium"
                                style={{ background: '#FEE2E2', color: '#DC2626' }}>{d}</span>
                            ))}
                          </div>
                        ) : <p className="text-xs" style={{ color: '#10B981' }}>✓ No leaves this month</p>}
                      </>
                    )}

                    {/* Late Comings */}
                    {key === 'late_comings' && (
                      <>
                        <div className="flex gap-6 text-sm mb-3 flex-wrap">
                          <span style={{ color: 'var(--text-muted)' }}>Working days: <b style={{ color: 'var(--text)' }}>{o.working_days ?? '—'}</b></span>
                          <span style={{ color: '#10B981' }}>On-time: <b>{o.on_time_days ?? '—'}</b></span>
                          <span style={{ color: o.late_days > 0 ? '#EF4444' : '#10B981' }}>Late: <b>{o.late_days ?? 0}</b></span>
                
                        </div>
                        {(o.late_entries || []).length > 0 ? (
                          <table className="w-full text-xs">
                            <thead><tr style={{ borderBottom: '1px solid var(--border)' }}>
                              {['Date','Shift Start (IST)','Punch In (IST)','Delay'].map((h,i) => (
                                <th key={i} className="text-left py-1.5 pr-4 font-semibold" style={{ color: 'var(--text-faint)' }}>{h}</th>
                              ))}
                            </tr></thead>
                            <tbody>{(o.late_entries).map((e, i) => {
                              const toIST = s => { if (!s) return '—'; const m = /(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})/.exec(s); if (!m) return s; const h = parseInt(m[4],10), mi = parseInt(m[5],10); const p = h>=12?'pm':'am'; const dh = h%12===0?12:h%12; return `${String(dh).padStart(2,'0')}:${String(mi).padStart(2,'0')} ${p}` }
                              let delay = '—'; try { const parseLocal = s => new Date((s||'').replace(' IST','')); const d = Math.round((parseLocal(e.punch_in) - parseLocal(e.shift_start))/60000); if(d>0) delay=`+${d} min` } catch {}
                              return (
                                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                                  <td className="py-1.5 pr-4 font-medium" style={{ color: 'var(--text)' }}>{e.date}</td>
                                  <td className="py-1.5 pr-4 tabular-nums" style={{ color: 'var(--text-muted)' }}>{toIST(e.shift_start)}</td>
                                  <td className="py-1.5 pr-4 tabular-nums font-medium" style={{ color: '#EF4444' }}>{toIST(e.punch_in)}</td>
                                  <td className="py-1.5 font-bold" style={{ color: '#EF4444' }}>{delay}</td>
                                </tr>
                              )
                            })}</tbody>
                          </table>
                        ) : <p className="text-xs" style={{ color: '#10B981' }}>✓ No late arrivals this month</p>}
                      </>
                    )}

                    {/* Early Leavings */}
                    {key === 'early_leavings' && (
                      <>
                        <div className="flex gap-6 text-sm mb-3 flex-wrap">
                          <span style={{ color: 'var(--text-muted)' }}>Working days: <b style={{ color: 'var(--text)' }}>{o.working_days ?? '—'}</b></span>
                          <span style={{ color: '#10B981' }}>Full days: <b>{o.full_days ?? '—'}</b></span>
                          <span style={{ color: o.early_days > 0 ? '#EF4444' : '#10B981' }}>Early exits: <b>{o.early_days ?? 0}</b></span>
                        </div>
                        {(o.early_entries || []).length > 0 ? (
                          <table className="w-full text-xs">
                            <thead><tr style={{ borderBottom: '1px solid var(--border)' }}>
                              {['Date','Expected','Actual','Shortfall'].map((h,i) => (
                                <th key={i} className="text-left py-1.5 pr-4 font-semibold" style={{ color: 'var(--text-faint)' }}>{h}</th>
                              ))}
                            </tr></thead>
                            <tbody>{(o.early_entries).map((e, i) => (
                              <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                                <td className="py-1.5 pr-4 font-medium" style={{ color: 'var(--text)' }}>{e.date}</td>
                                <td className="py-1.5 pr-4" style={{ color: 'var(--text-muted)' }}>{e.expected_hours}h</td>
                                <td className="py-1.5 pr-4 font-medium" style={{ color: '#EF4444' }}>{e.actual_hours}h</td>
                                <td className="py-1.5 font-bold" style={{ color: '#EF4444' }}>-{e.shortfall_hrs}h</td>
                              </tr>
                            ))}</tbody>
                          </table>
                        ) : <p className="text-xs" style={{ color: '#10B981' }}>✓ No early exits this month</p>}
                      </>
                    )}

                    {/* Independence */}
                    {key === 'independence' && (
                      <div className="flex gap-8 text-sm">
                        <span style={{ color: 'var(--text-muted)' }}>Rating: <b style={{ color: '#6366F1' }}>{o.rating ?? 'Not rated'}</b></span>
                        <span style={{ color: 'var(--text-muted)' }}>Score: <b style={{ color: '#6366F1' }}>{o.score_pct ?? '—'}%</b></span>
                        {o.rated_by && <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>Rated by: {o.rated_by}</span>}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )
      })()}

      {/* ── Completed files table ────────────────────────────────── */}
      {files.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
            <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>
              Completed Files — {monthName(month)} {year}
              <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full"
                style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)' }}>
                {files.length} files
              </span>
            </p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              Files that affected this employee's KPI scores
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--bg)', borderBottom: '1px solid var(--border)' }}>
                  {['#','Order #','Company','Completed','Post Conversion','Delayed','Not Updated'].map((h, i) => (
                    <th key={i} className="px-4 py-2.5 text-left text-xs font-semibold"
                      style={{ color: 'var(--text-faint)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {files.map((f, i) => (
                  <tr key={f.oid} className="border-b"
                    style={{ borderColor: 'var(--border)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <td className="px-4 py-2.5 text-xs font-mono" style={{ color: 'var(--text-faint)' }}>{i + 1}</td>
                    <td className="px-4 py-2.5 font-mono text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                      {f.num}
                    </td>
                    <td className="px-4 py-2.5 max-w-[180px] truncate font-medium" style={{ color: 'var(--text)' }}>
                      {f.company}
                    </td>
                    <td className="px-4 py-2.5 tabular-nums text-xs" style={{ color: 'var(--text-muted)' }}>
                      {f.completed}
                    </td>
                    <td className="px-4 py-2.5">
                      {f.post !== null ? (
                        <span className="flex items-center gap-1 text-xs font-medium"
                          style={{ color: f.post === 'Issue' ? '#EF4444' : '#10B981' }}>
                          {f.post === 'Issue' ? <><XCircle size={12}/> Issue</> : <><CheckCircle size={12}/> Clean</>}
                        </span>
                      ) : <span style={{ color: 'var(--text-faint)', fontSize: 18 }}>·</span>}
                    </td>
                    <td className="px-4 py-2.5">
                      {f.delayed !== null ? (
                        <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                          style={{
                            background: f.delayed === 'Delayed' ? '#FEE2E2' : f.delayed === 'No ETA' ? '#FEF3C7' : '#DCFCE7',
                            color: f.delayed === 'Delayed' ? '#DC2626' : f.delayed === 'No ETA' ? '#D97706' : '#15803D',
                          }}>
                          {f.delayed}
                        </span>
                      ) : <span style={{ color: 'var(--text-faint)', fontSize: 18 }}>·</span>}
                    </td>
                    <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                      {f.missing !== null && f.missing !== undefined ? (
                        <span className="flex items-center gap-1 font-semibold"
                          style={{ color: (f.missing_missed || 0) === 0 ? '#10B981' :
                            (f.missing_missed / (f.missing_active || 1)) > 0.3 ? '#EF4444' : '#F59E0B' }}>
                          <Clock size={11}/> {f.missing}
                        </span>
                      ) : <span style={{ color: 'var(--text-faint)', fontSize: 18 }}>·</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// import { useEffect, useState } from 'react'
// import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
// import {
//   LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
//   ResponsiveContainer, BarChart, Bar, Cell,
// } from 'recharts'
// import { ArrowLeft, CheckCircle, XCircle, Clock } from 'lucide-react'
// import { monthName, fmtScore } from '../utils/formatters'
// import toast from 'react-hot-toast'

// const TIER_COLOR  = { A: '#10B981', B: '#F59E0B', C: '#EF4444' }
// const KPI_COLORS  = ['#6366F1','#10B981','#F59E0B','#EF4444','#8B5CF6','#06B6D4','#EC4899','#14B8A6']
// const MONTH_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

// function ScoreCircle({ score, tier }) {
//   const c    = TIER_COLOR[tier] ?? '#6366F1'
//   const r    = 52, cx = 64, cy = 64
//   const circ = 2 * Math.PI * r
//   const dash = circ * (Math.min(score, 100) / 100)
//   return (
//     <svg width={128} height={128}>
//       <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--border)" strokeWidth={8}
//         style={{ transform: 'rotate(-90deg)', transformOrigin: '50% 50%' }}/>
//       <circle cx={cx} cy={cy} r={r} fill="none" stroke={c} strokeWidth={8}
//         strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
//         style={{ transform: 'rotate(-90deg)', transformOrigin: '50% 50%', transition: 'stroke-dasharray 0.8s' }}/>
//       <text x={cx} y={cy - 4} textAnchor="middle" fill={c}
//         style={{ fontSize: 24, fontWeight: 300 }}>{fmtScore(score)}</text>
//       <text x={cx} y={cy + 16} textAnchor="middle" fill="var(--text-faint)"
//         style={{ fontSize: 11 }}>/ 100</text>
//     </svg>
//   )
// }

// export default function EmployeeDetail() {
//   const { id }     = useParams()
//   const [sp]       = useSearchParams()
//   const navigate   = useNavigate()
//   const [month, setMonth] = useState(parseInt(sp.get('month') || new Date().getMonth() + 1))
//   const [year,  setYear]  = useState(parseInt(sp.get('year')  || 2026))
//   const [detail,  setDetail]  = useState(null)
//   const [trend,   setTrend]   = useState([])
//   const [loading, setLoading] = useState(true)
//   const [trendOk, setTrendOk] = useState(false)

//   useEffect(() => {
//     setLoading(true)
//     fetch(`/api/scores/${id}?month=${month}&year=${year}`, { credentials: 'include' })
//       .then(r => r.ok ? r.json() : Promise.reject(r.status))
//       .then(d => { setDetail(d); setLoading(false) })
//       .catch(e => { toast.error(`Load failed: ${e}`); setLoading(false) })
//   }, [id, month, year])

//   useEffect(() => {
//     fetch(`/api/scores/${id}/trend?year=${year}`, { credentials: 'include' })
//       .then(r => r.ok ? r.json() : Promise.reject(r.status))
//       .then(d => {
//         setTrend((d.trend || []).map(t => ({
//           m: MONTH_SHORT[t.month - 1],
//           score: t.total_score,
//         })))
//         setTrendOk(true)
//       })
//       .catch(() => setTrendOk(false))
//   }, [id, year])

//   if (loading) return (
//     <div className="flex items-center justify-center py-24">
//       <div className="w-10 h-10 rounded-full animate-spin"
//         style={{ border: '3px solid var(--border)', borderTopColor: '#6366F1' }}/>
//     </div>
//   )
//   if (!detail) return (
//     <div className="text-center py-20" style={{ color: 'var(--text-muted)' }}>Employee not found.</div>
//   )

//   const tc   = TIER_COLOR[detail.tier?.grade] ?? '#6366F1'
//   const kpis = Object.entries(detail.kpi_breakdown || {})
//   const barData = kpis.map(([, k], i) => ({
//     name: k.name.split(' ').slice(0, 2).join(' '),
//     value: +(100 - (k.success_ratio ?? 100)).toFixed(1),  // failure ratio
//     fill: KPI_COLORS[i % KPI_COLORS.length],
//   }))

//   // Merge orders across KPIs into unified file table
//   const fileMap = {}
//   kpis.forEach(([key, kpi]) => {
//     ;(kpi.orders || []).forEach(o => {
//       const oid = o.order_id || o.OrderID
//       if (!oid) return
//       if (!fileMap[oid]) {
//         fileMap[oid] = {
//           oid,
//           num:       o.order_number || o.OrderNumber || String(oid),
//           company:   o.company || o.CompanyName || '—',
//           completed: o.completed || o.FinalCompletionDate || '—',
//           post:  null, delayed: null, missing: null,
//         }
//       }
//       if (key === 'post_conversion') {
//         fileMap[oid].post = o.issue || 'Clean'
//         // Always update completed from post_conversion — it has the most accurate date logic
//         if (o.completed && o.completed !== '—') fileMap[oid].completed = o.completed
//       }
//       if (key === 'delayed_conversion') {
//         fileMap[oid].delayed = o.status || 'No ETA'
//         if (o.completed && o.completed !== '—') fileMap[oid].completed = o.completed
//       }
//       if (key === 'missing_status' && o._is_file_entry && oid) {
//         if (fileMap[oid]) {
//           const activeDays = o.ActiveDays || o.active_days || 0
//           fileMap[oid].missing        = `${o.DaysMissed || 0}/${activeDays}d`
//           fileMap[oid].missing_missed = o.DaysMissed || 0
//           fileMap[oid].missing_active = activeDays
//         }
//       }
//     })
//   })
//   const files = Object.values(fileMap).sort((a, b) =>
//     String(a.completed).localeCompare(String(b.completed)))

//   return (
//     <div className="space-y-5">
//       <button onClick={() => navigate(-1)}
//         className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
//         <ArrowLeft size={15}/> Back
//       </button>

//       {/* ── Hero ──────────────────────────────────────────────────── */}
//       <div className="card p-6 flex items-center gap-6 flex-wrap">
//         <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-bold text-white"
//           style={{ background: tc }}>
//           {detail.employee_name?.[0]}
//         </div>
//         <div className="flex-1 min-w-0">
//           <h1 className="text-2xl font-bold" style={{ color: 'var(--text)' }}>{detail.employee_name}</h1>
//           <div className="flex items-center gap-3 mt-1 flex-wrap">
//             <span className="text-sm px-3 py-1 rounded-full font-bold"
//               style={{ background: `${tc}18`, color: tc }}>
//               Tier {detail.tier?.grade} — {detail.tier?.label}
//             </span>
//             <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
//               {monthName(month)} {year}
//             </span>
//           </div>
//         </div>
//         <ScoreCircle score={detail.total_score} tier={detail.tier?.grade}/>
//       </div>

//       {/* ── Year trend line chart ─────────────────────────────────── */}
//       <div className="card p-5">
//         <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
//           <div>
//             <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>
//               {year} Score Trend
//             </p>
//             <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
//               Monthly performance — click a month to load its data
//             </p>
//           </div>
//           <div className="flex gap-1">
//             {[2025, 2026].map(y => (
//               <button key={y} onClick={() => setYear(y)}
//                 className="text-xs px-3 py-1 rounded-lg transition-colors"
//                 style={{
//                   background: year === y ? '#EEF2FF' : 'var(--bg-hover)',
//                   color: year === y ? '#6366F1' : 'var(--text-muted)',
//                   fontWeight: year === y ? 600 : 400,
//                 }}>{y}</button>
//             ))}
//           </div>
//         </div>
//         <div style={{ height: 200 }}>
//           <ResponsiveContainer width="100%" height="100%">
//             <LineChart data={trend} margin={{ left: 0, right: 20, top: 8, bottom: 0 }}>
//               <CartesianGrid strokeDasharray="3 3" stroke="var(--border)"/>
//               <XAxis dataKey="m" tick={{ fill: 'var(--text-muted)', fontSize: 12 }}/>
//               <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 12 }}/>
//               <Tooltip
//                 contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, fontSize: 13 }}
//                 formatter={v => [v !== null ? `${v}` : 'No data', 'Score']}/>
//               <Line type="monotone" dataKey="score" stroke={tc} strokeWidth={2.5}
//                 dot={{ fill: tc, r: 4, strokeWidth: 0 }} connectNulls={false}/>
//             </LineChart>
//           </ResponsiveContainer>
//         </div>
//         {/* Month pills */}
//         <div className="flex gap-1 mt-3 flex-wrap">
//           {MONTH_SHORT.map((m, i) => {
//             const mn = i + 1
//             const isActive = mn === month
//             return (
//               <button key={m} onClick={() => setMonth(mn)}
//                 className="text-xs px-2.5 py-1 rounded-lg transition-colors"
//                 style={{
//                   background: isActive ? tc : 'var(--bg-hover)',
//                   color: isActive ? '#fff' : 'var(--text-muted)',
//                   fontWeight: isActive ? 600 : 400,
//                 }}>{m}</button>
//             )
//           })}
//         </div>
//       </div>

//       {/* ── KPI bar chart + detail cards ─────────────────────────── */}
//       <div className="card p-5">
//         <p className="font-semibold text-sm mb-4" style={{ color: 'var(--text)' }}>
//           KPI Failure Rates
//           <span className="ml-2 text-xs font-normal" style={{ color: 'var(--text-muted)' }}>
//             Problem areas this month — lower is better
//           </span>
//         </p>
//         <div style={{ height: 170 }}>
//           <ResponsiveContainer width="100%" height="100%">
//             <BarChart data={barData} layout="vertical" margin={{ left: 110, right: 70, top: 0, bottom: 0 }}>
//               <XAxis type="number" domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
//                 tickFormatter={v => `${v}%`}/>
//               <YAxis type="category" dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} width={105}/>
//               <Tooltip
//                 contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, fontSize: 13 }}
//                 formatter={(v, _, props) => [`${v}% failure rate`, props.payload.name]}/>
//               <Bar dataKey="value" radius={[0, 4, 4, 0]} fillOpacity={0.85}
//                 label={{ position: 'right', fontSize: 12, fill: 'var(--text-muted)', formatter: v => `${v}%` }}>
//                 {barData.map((d, i) => <Cell key={i} fill={d.fill} fillOpacity={0.82}/>)}
//               </Bar>
//             </BarChart>
//           </ResponsiveContainer>
//         </div>

//         <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-5">
//           {kpis.map(([key, kpi], i) => {
//             const c = KPI_COLORS[i % KPI_COLORS.length]
//             return (
//               <div key={key} className="rounded-xl p-4 border" style={{ borderColor: 'var(--border)' }}>
//                 <div className="flex items-start justify-between mb-2">
//                   <p className="font-semibold text-sm pr-2" style={{ color: 'var(--text)' }}>{kpi.name}</p>
//                   <span className="text-lg font-light shrink-0" style={{ color: c }}>
//                     {kpi.success_ratio !== null ? `${(100-kpi.success_ratio).toFixed(1)}%` : 'N/A'}
//                     <span className="text-xs ml-1 font-normal" style={{ color: 'var(--text-faint)' }}>failure rate</span>
//                   </span>
//                 </div>
//                 <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>{kpi.description}</p>
//                 <div className="h-1.5 rounded-full overflow-hidden mb-2" style={{ background: 'var(--border)' }}>
//                   <div className="h-full rounded-full" style={{ width: `${100-(kpi.success_ratio ?? 100)}%`, background: c }}/>
//                 </div>
//                 <div className="flex items-center justify-between text-xs">
//                   <span style={{ color: 'var(--text-muted)' }}>
//                     {/* Show failure count: denominator - numerator / denominator */}
//                     {kpi.denominator > 0
//                       ? `${kpi.denominator - kpi.numerator} / ${kpi.denominator}`
//                       : '— / —'}
//                   </span>
//                   <span className="px-2 py-0.5 rounded-full font-bold text-[10px]"
//                     style={{ background: `${c}18`, color: c }}>
//                     Weight: {kpi.weight?.toFixed(1)}%
//                   </span>
//                 </div>
//                 <div className="flex items-center justify-between mt-2 pt-2 border-t text-xs"
//                   style={{ borderColor: 'var(--border)' }}>
//                   <span style={{ color: 'var(--text-faint)' }}>Score</span>
//                   <span className="font-semibold" style={{ color: tc }}>
//                     {kpi.score !== null ? kpi.score.toFixed(2) : '—'}
//                   </span>
//                 </div>
//               </div>
//             )
//           })}
//         </div>
//       </div>


//       {/* ── Attendance Detail ────────────────────────────────────── */}
//       {(() => {
//         const attendanceKPIs = ['missing_status','leaves','late_comings','early_leavings','independence']
//         const attKpis = kpis.filter(([key]) => attendanceKPIs.includes(key))
//         if (!attKpis.length) return null
//         return (
//           <div className="card p-5">
//             <p className="font-semibold text-sm mb-4" style={{ color: 'var(--text)' }}>
//               Attendance Detail
//               <span className="ml-2 text-xs font-normal" style={{ color: 'var(--text-muted)' }}>
//                 {monthName(month)} {year}
//               </span>
//             </p>
//             <div className="space-y-4">
//               {attKpis.map(([key, kpi]) => {
//                 const o = kpi.orders?.[0]
//                 if (!o) return null
//                 const KPI_LABEL = {
//                   missing_status: 'Status Not Updated', leaves: 'Leaves',
//                   late_comings: 'Late Comings',
//                   early_leavings: 'Early Leavings', independence: 'Independence'
//                 }
//                 return (
//                   <div key={key} className="rounded-xl p-4 border" style={{ borderColor: 'var(--border)' }}>
//                     <p className="font-semibold text-sm mb-3" style={{ color: 'var(--text)' }}>
//                       {KPI_LABEL[key]}
//                     </p>

//                     {/* Missing Status — summary + per-file table */}
//                     {key === 'missing_status' && (
//                       <>
//                         {/* Summary row — Option A scoring */}
//                         <div className="flex gap-8 text-sm mb-4 flex-wrap">
//                           <span style={{ color: 'var(--text-muted)' }}>
//                             Working days: <b style={{ color: 'var(--text)' }}>{o.TotalActiveDays ?? '—'}</b>
//                           </span>
//                           <span style={{ color: '#10B981' }}>
//                             Days updated: <b>{o.DaysWithUpdate ?? '—'}</b>
//                           </span>
//                           <span style={{ color: o.MissedDays > 0 ? '#EF4444' : '#10B981' }}>
//                             Days missed: <b>{o.MissedDays ?? '—'}</b>
//                           </span>
//                         </div>

//                         {/* Per-file breakdown table */}
//                         {(o.file_breakdown || []).length > 0 ? (
//                           <div className="overflow-x-auto">
//                             <table className="w-full text-xs">
//                               <thead>
//                                 <tr style={{ borderBottom: '2px solid var(--border)',
//                                              background: 'var(--bg)' }}>
//                                   {['Order #','Company','Completed','Active From',
//                                     'Active Days','Updated','Missed','Status'].map((h,i) => (
//                                     <th key={i}
//                                       className="text-left py-2 pr-4 font-bold tracking-wide"
//                                       style={{ color: 'var(--text-faint)', fontSize: 10,
//                                                textTransform: 'uppercase' }}>{h}</th>
//                                   ))}
//                                 </tr>
//                               </thead>
//                               <tbody>
//                                 {o.file_breakdown.map((fb, i) => {
//                                   const pct = fb.active_days > 0
//                                     ? (fb.days_missed / fb.active_days) * 100 : 0
//                                   const color = fb.days_missed === 0 ? '#10B981'
//                                     : pct <= 30 ? '#F59E0B' : '#EF4444'
//                                   const dot = fb.days_missed === 0 ? '🟢'
//                                     : pct <= 30 ? '🟡' : '🔴'
//                                   return (
//                                     <tr key={i}
//                                       style={{ borderBottom: '1px solid var(--border)' }}
//                                       onMouseEnter={e=>e.currentTarget.style.background='var(--bg-hover)'}
//                                       onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
//                                       <td className="py-2 pr-4 font-mono"
//                                         style={{ color:'var(--text-muted)', fontSize:10 }}>
//                                         {fb.order_number}
//                                       </td>
//                                       <td className="py-2 pr-4 max-w-[180px] truncate font-medium"
//                                         style={{ color:'var(--text)' }}>{fb.company}</td>
//                                       <td className="py-2 pr-4 tabular-nums"
//                                         style={{ color:'var(--text-muted)' }}>{fb.completed}</td>
//                                       <td className="py-2 pr-4 tabular-nums"
//                                         style={{ color:'var(--text-muted)' }}>{fb.active_from}</td>
//                                       <td className="py-2 pr-4 tabular-nums text-center font-medium"
//                                         style={{ color:'var(--text)' }}>{fb.active_days}</td>
//                                       <td className="py-2 pr-4 tabular-nums text-center font-bold"
//                                         style={{ color:'#10B981' }}>{fb.days_updated}</td>
//                                       <td className="py-2 pr-4 tabular-nums text-center font-bold"
//                                         style={{ color: fb.days_missed > 0 ? '#EF4444':'#10B981' }}>
//                                         {fb.days_missed}
//                                       </td>
//                                       <td className="py-2 tabular-nums font-bold text-xs"
//                                         style={{ color, whiteSpace:'nowrap' }}>
//                                         {dot} {fb.days_updated}/{fb.active_days}
//                                       </td>
//                                     </tr>
//                                   )
//                                 })}
//                               </tbody>
//                               {/* Totals row */}
//                               {(() => {
//                                 const totalActive  = o.file_breakdown.reduce((s,f)=>s+f.active_days,0)
//                                 const totalUpdated = o.file_breakdown.reduce((s,f)=>s+f.days_updated,0)
//                                 const totalMissed  = o.file_breakdown.reduce((s,f)=>s+f.days_missed,0)
//                                 return (
//                                   <tfoot>
//                                     <tr style={{ borderTop:'2px solid var(--border)',
//                                                  background:'var(--bg-hover)' }}>
//                                       <td colSpan={4} className="py-2 pr-4 font-bold text-xs"
//                                         style={{ color:'var(--text)' }}>
//                                         TOTAL ({o.file_breakdown.length} files)
//                                       </td>
//                                       <td className="py-2 pr-4 text-center font-bold tabular-nums"
//                                         style={{ color:'var(--text)' }}>{totalActive}</td>
//                                       <td className="py-2 pr-4 text-center font-bold tabular-nums"
//                                         style={{ color:'#10B981' }}>{totalUpdated}</td>
//                                       <td className="py-2 pr-4 text-center font-bold tabular-nums"
//                                         style={{ color: totalMissed>0?'#EF4444':'#10B981' }}>
//                                         {totalMissed}
//                                       </td>
//                                       <td className="py-2 font-bold text-xs"
//                                         style={{ color: totalMissed>0?'#EF4444':'#10B981' }}>
//                                         {totalUpdated}/{totalActive}
//                                       </td>
//                                     </tr>
//                                   </tfoot>
//                                 )
//                               })()}
//                             </table>
//                           </div>
//                         ) : (
//                           <p className="text-xs italic" style={{ color:'var(--text-faint)' }}>
//                             No completed files this month.
//                           </p>
//                         )}
//                       </>
//                     )}

//                     {/* Leaves */}
//                     {key === 'leaves' && (
//                       <>
//                         <div className="flex gap-6 text-sm mb-3 flex-wrap">
//                           <span style={{ color: 'var(--text-muted)' }}>Working days: <b style={{ color: 'var(--text)' }}>{o.working_days ?? '—'}</b></span>
//                           <span style={{ color: '#10B981' }}>Present: <b>{o.present_days ?? '—'}</b></span>
//                           <span style={{ color: o.leave_days > 0 ? '#EF4444' : '#10B981' }}>Leaves: <b>{o.leave_days ?? 0}</b></span>
//                         </div>
//                         {(o.leave_dates || []).length > 0 ? (
//                           <div className="flex flex-wrap gap-1.5">
//                             {o.leave_dates.map((d, i) => (
//                               <span key={i} className="text-xs px-2 py-0.5 rounded-lg font-medium"
//                                 style={{ background: '#FEE2E2', color: '#DC2626' }}>{d}</span>
//                             ))}
//                           </div>
//                         ) : <p className="text-xs" style={{ color: '#10B981' }}>✓ No leaves this month</p>}
//                       </>
//                     )}

//                     {/* Late Comings */}
//                     {key === 'late_comings' && (
//                       <>
//                         <div className="flex gap-6 text-sm mb-3 flex-wrap">
//                           <span style={{ color: 'var(--text-muted)' }}>Working days: <b style={{ color: 'var(--text)' }}>{o.working_days ?? '—'}</b></span>
//                           <span style={{ color: '#10B981' }}>On-time: <b>{o.on_time_days ?? '—'}</b></span>
//                           <span style={{ color: o.late_days > 0 ? '#EF4444' : '#10B981' }}>Late: <b>{o.late_days ?? 0}</b></span>
                
//                         </div>
//                         {(o.late_entries || []).length > 0 ? (
//                           <table className="w-full text-xs">
//                             <thead><tr style={{ borderBottom: '1px solid var(--border)' }}>
//                               {['Date','Shift Start (IST)','Punch In (IST)','Delay'].map((h,i) => (
//                                 <th key={i} className="text-left py-1.5 pr-4 font-semibold" style={{ color: 'var(--text-faint)' }}>{h}</th>
//                               ))}
//                             </tr></thead>
//                             <tbody>{(o.late_entries).map((e, i) => {
//                               const toIST = s => { try { return new Date(s.replace(' UTC','Z')).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'}) } catch { return s } }
//                               let delay = '—'; try { const d = Math.round((new Date(e.punch_in?.replace(' UTC','Z')) - new Date(e.shift_start?.replace(' UTC','Z')))/60000); if(d>0) delay=`+${d} min` } catch {}
//                               return (
//                                 <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
//                                   <td className="py-1.5 pr-4 font-medium" style={{ color: 'var(--text)' }}>{e.date}</td>
//                                   <td className="py-1.5 pr-4 tabular-nums" style={{ color: 'var(--text-muted)' }}>{toIST(e.shift_start)}</td>
//                                   <td className="py-1.5 pr-4 tabular-nums font-medium" style={{ color: '#EF4444' }}>{toIST(e.punch_in)}</td>
//                                   <td className="py-1.5 font-bold" style={{ color: '#EF4444' }}>{delay}</td>
//                                 </tr>
//                               )
//                             })}</tbody>
//                           </table>
//                         ) : <p className="text-xs" style={{ color: '#10B981' }}>✓ No late arrivals this month</p>}
//                       </>
//                     )}

//                     {/* Early Leavings */}
//                     {key === 'early_leavings' && (
//                       <>
//                         <div className="flex gap-6 text-sm mb-3 flex-wrap">
//                           <span style={{ color: 'var(--text-muted)' }}>Working days: <b style={{ color: 'var(--text)' }}>{o.working_days ?? '—'}</b></span>
//                           <span style={{ color: '#10B981' }}>Full days: <b>{o.full_days ?? '—'}</b></span>
//                           <span style={{ color: o.early_days > 0 ? '#EF4444' : '#10B981' }}>Early exits: <b>{o.early_days ?? 0}</b></span>
//                         </div>
//                         {(o.early_entries || []).length > 0 ? (
//                           <table className="w-full text-xs">
//                             <thead><tr style={{ borderBottom: '1px solid var(--border)' }}>
//                               {['Date','Expected','Actual','Shortfall'].map((h,i) => (
//                                 <th key={i} className="text-left py-1.5 pr-4 font-semibold" style={{ color: 'var(--text-faint)' }}>{h}</th>
//                               ))}
//                             </tr></thead>
//                             <tbody>{(o.early_entries).map((e, i) => (
//                               <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
//                                 <td className="py-1.5 pr-4 font-medium" style={{ color: 'var(--text)' }}>{e.date}</td>
//                                 <td className="py-1.5 pr-4" style={{ color: 'var(--text-muted)' }}>{e.expected_hours}h</td>
//                                 <td className="py-1.5 pr-4 font-medium" style={{ color: '#EF4444' }}>{e.actual_hours}h</td>
//                                 <td className="py-1.5 font-bold" style={{ color: '#EF4444' }}>-{e.shortfall_hrs}h</td>
//                               </tr>
//                             ))}</tbody>
//                           </table>
//                         ) : <p className="text-xs" style={{ color: '#10B981' }}>✓ No early exits this month</p>}
//                       </>
//                     )}

//                     {/* Independence */}
//                     {key === 'independence' && (
//                       <div className="flex gap-8 text-sm">
//                         <span style={{ color: 'var(--text-muted)' }}>Rating: <b style={{ color: '#6366F1' }}>{o.rating ?? 'Not rated'}</b></span>
//                         <span style={{ color: 'var(--text-muted)' }}>Score: <b style={{ color: '#6366F1' }}>{o.score_pct ?? '—'}%</b></span>
//                         {o.rated_by && <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>Rated by: {o.rated_by}</span>}
//                       </div>
//                     )}
//                   </div>
//                 )
//               })}
//             </div>
//           </div>
//         )
//       })()}

//       {/* ── Completed files table ────────────────────────────────── */}
//       {files.length > 0 && (
//         <div className="card overflow-hidden">
//           <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
//             <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>
//               Completed Files — {monthName(month)} {year}
//               <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full"
//                 style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)' }}>
//                 {files.length} files
//               </span>
//             </p>
//             <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
//               Files that affected this employee's KPI scores
//             </p>
//           </div>
//           <div className="overflow-x-auto">
//             <table className="w-full text-sm">
//               <thead>
//                 <tr style={{ background: 'var(--bg)', borderBottom: '1px solid var(--border)' }}>
//                   {['#','Order #','Company','Completed','Post Conversion','Delayed','Not Updated'].map((h, i) => (
//                     <th key={i} className="px-4 py-2.5 text-left text-xs font-semibold"
//                       style={{ color: 'var(--text-faint)' }}>{h}</th>
//                   ))}
//                 </tr>
//               </thead>
//               <tbody>
//                 {files.map((f, i) => (
//                   <tr key={f.oid} className="border-b"
//                     style={{ borderColor: 'var(--border)' }}
//                     onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
//                     onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
//                     <td className="px-4 py-2.5 text-xs font-mono" style={{ color: 'var(--text-faint)' }}>{i + 1}</td>
//                     <td className="px-4 py-2.5 font-mono text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
//                       {f.num}
//                     </td>
//                     <td className="px-4 py-2.5 max-w-[180px] truncate font-medium" style={{ color: 'var(--text)' }}>
//                       {f.company}
//                     </td>
//                     <td className="px-4 py-2.5 tabular-nums text-xs" style={{ color: 'var(--text-muted)' }}>
//                       {f.completed}
//                     </td>
//                     <td className="px-4 py-2.5">
//                       {f.post !== null ? (
//                         <span className="flex items-center gap-1 text-xs font-medium"
//                           style={{ color: f.post === 'Issue' ? '#EF4444' : '#10B981' }}>
//                           {f.post === 'Issue' ? <><XCircle size={12}/> Issue</> : <><CheckCircle size={12}/> Clean</>}
//                         </span>
//                       ) : <span style={{ color: 'var(--text-faint)', fontSize: 18 }}>·</span>}
//                     </td>
//                     <td className="px-4 py-2.5">
//                       {f.delayed !== null ? (
//                         <span className="text-xs font-medium px-2 py-0.5 rounded-full"
//                           style={{
//                             background: f.delayed === 'Delayed' ? '#FEE2E2' : f.delayed === 'No ETA' ? '#FEF3C7' : '#DCFCE7',
//                             color: f.delayed === 'Delayed' ? '#DC2626' : f.delayed === 'No ETA' ? '#D97706' : '#15803D',
//                           }}>
//                           {f.delayed}
//                         </span>
//                       ) : <span style={{ color: 'var(--text-faint)', fontSize: 18 }}>·</span>}
//                     </td>
//                     <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-muted)' }}>
//                       {f.missing !== null && f.missing !== undefined ? (
//                         <span className="flex items-center gap-1 font-semibold"
//                           style={{ color: (f.missing_missed || 0) === 0 ? '#10B981' :
//                             (f.missing_missed / (f.missing_active || 1)) > 0.3 ? '#EF4444' : '#F59E0B' }}>
//                           <Clock size={11}/> {f.missing}
//                         </span>
//                       ) : <span style={{ color: 'var(--text-faint)', fontSize: 18 }}>·</span>}
//                     </td>
//                   </tr>
//                 ))}
//               </tbody>
//             </table>
//           </div>
//         </div>
//       )}
//     </div>
//   )
// }

