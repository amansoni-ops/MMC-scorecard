import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  LineChart, Line, CartesianGrid, XAxis, YAxis, Legend,
} from 'recharts'
import * as XLSX from 'xlsx'
import { Download, RotateCcw, ChevronRight, Loader, CheckCircle, Clock } from 'lucide-react'
import { monthName, fmtScore, fmtPct } from '../utils/formatters'
import toast from 'react-hot-toast'

const TIER_COLOR  = { A: '#10B981', B: '#F59E0B', C: '#EF4444' }
const KPI_COLORS  = ['#6366F1', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899']
const YEARS       = [2026, 2025, 2024]
const ALL_MONTHS  = [1,2,3,4,5,6,7,8,9,10,11,12]

// ── Single month pill/button ───────────────────────────────────────────────
function MonthBtn({ month, status, onClick }) {
  const cfg = {
    idle:    { bg: 'var(--bg-hover)',  border: 'var(--border)',  color: 'var(--text-muted)', cursor: 'pointer' },
    loading: { bg: '#EEF2FF',          border: '#A5B4FC',         color: '#4338CA',           cursor: 'wait'    },
    done:    { bg: '#DCFCE7',          border: '#86EFAC',         color: '#15803D',           cursor: 'pointer' },
    error:   { bg: '#FEE2E2',          border: '#FCA5A5',         color: '#B91C1C',           cursor: 'pointer' },
  }[status] ?? { bg: 'var(--bg-hover)', border: 'var(--border)', color: 'var(--text-muted)', cursor: 'pointer' }

  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.97 }}
      onClick={onClick}
      disabled={status === 'loading'}
      className="flex flex-col items-center gap-1.5 p-0"
      style={{ cursor: cfg.cursor, background: 'none', border: 'none' }}
    >
      <div className="w-12 h-12 rounded-xl flex items-center justify-center font-bold text-sm relative"
        style={{ background: cfg.bg, border: `1.5px solid ${cfg.border}`, color: cfg.color, transition: 'all 0.2s' }}>
        {status === 'loading'
          ? <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
              <Loader size={16} />
            </motion.div>
          : status === 'done' ? <CheckCircle size={16} />
          : status === 'error' ? '!'
          : <span>{month}</span>}

        {status === 'done' && (
          <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}
            className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-green-500"
            style={{ border: '2px solid var(--bg-card)' }} />
        )}
      </div>
      <span className="text-[10px] font-semibold" style={{ color: cfg.color }}>
        {monthName(month).slice(0, 3)}
      </span>
    </motion.button>
  )
}

// ── Month card shown after loading ────────────────────────────────────────
function MonthCard({ month, year, employees, kpis, onViewDashboard }) {
  const total  = employees.length
  const tiers  = {
    A: employees.filter(e => e.tier?.grade === 'A').length,
    B: employees.filter(e => e.tier?.grade === 'B').length,
    C: employees.filter(e => e.tier?.grade === 'C').length,
  }
  const avg  = total ? employees.reduce((s,e) => s + e.total_score, 0) / total : 0
  const top3 = employees.slice(0, 3)

  const donutData = ['A','B','C']
    .map(g => ({ name: `Tier ${g}`, value: tiers[g], fill: TIER_COLOR[g] }))
    .filter(d => d.value > 0)

  const kpiRows = kpis.filter(k => k.is_active).map((k, i) => ({
    name: k.name.split(' ').slice(0, 2).join(' '),
    key:  k.key,
    avg:  total > 0
      ? employees.reduce((s,e) => s + (e.kpi_breakdown?.[k.key]?.success_ratio ?? 0), 0) / total
      : 0,
    fill: KPI_COLORS[i % KPI_COLORS.length],
  }))

  return (
    <motion.div
      initial={{ opacity: 0, y: 24, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: 'spring', stiffness: 220, damping: 20 }}
      whileHover={{ y: -4 }}
      className="card overflow-hidden cursor-pointer group"
      onClick={() => onViewDashboard(month, year)}
    >
      {/* Top accent */}
      <div className="h-1" style={{ background: 'linear-gradient(90deg,#6366F1,#8B5CF6,#EC4899)' }} />

      {/* Header */}
      <div className="px-4 pt-3 pb-3 border-b flex items-center justify-between"
        style={{ borderColor: 'var(--border)', background: 'var(--bg)' }}>
        <div>
          <p className="font-bold text-base" style={{ color: 'var(--text)' }}>
            {monthName(month)} {year}
          </p>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {total} employees · avg {avg.toFixed(1)}
          </p>
        </div>
        <ChevronRight size={16} className="opacity-20 group-hover:opacity-60 transition-opacity"
          style={{ color: 'var(--text-faint)' }} />
      </div>

      <div className="p-4 space-y-4">

        {/* Donut + tier bars */}
        <div className="flex items-center gap-4">
          {/* Explicit size donut */}
          <div style={{ width: 80, height: 80, flexShrink: 0 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={donutData} cx="50%" cy="50%"
                  innerRadius={22} outerRadius={36} dataKey="value" paddingAngle={2}>
                  {donutData.map((d,i) => <Cell key={i} fill={d.fill} />)}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex-1 space-y-2">
            {['A','B','C'].map(g => (
              <div key={g} className="flex items-center gap-2">
                <span className="text-xs font-bold w-10" style={{ color: TIER_COLOR[g] }}>Tier {g}</span>
                <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                  <div className="h-full rounded-full transition-all duration-700"
                    style={{ width: total ? `${(tiers[g]/total)*100}%` : 0, background: TIER_COLOR[g] }} />
                </div>
                <span className="text-xs font-bold w-4 text-right" style={{ color: TIER_COLOR[g] }}>
                  {tiers[g]}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* KPI averages */}
        {kpiRows.length > 0 && (
          <div>
            <p className="text-[10px] font-bold tracking-widest mb-2" style={{ color: 'var(--text-faint)' }}>
              KPI AVERAGES
            </p>
            {kpiRows.map((k, i) => (
              <div key={i} className="flex items-center gap-2 mb-1.5">
                <div className="w-2 h-2 rounded-full shrink-0" style={{ background: k.fill }} />
                <span className="text-xs flex-1 truncate" style={{ color: 'var(--text-muted)' }}>{k.name}</span>
                <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                  <div className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${k.avg}%`, background: k.fill }} />
                </div>
                <span className="text-xs w-9 text-right tabular-nums" style={{ color: 'var(--text-muted)' }}>
                  {k.avg.toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Top 3 */}
        {top3.length > 0 && (
          <div>
            <p className="text-[10px] font-bold tracking-widest mb-2" style={{ color: 'var(--text-faint)' }}>
              TOP PERFORMERS
            </p>
            {top3.map((emp, i) => {
              const tc = TIER_COLOR[emp.tier?.grade] ?? '#6B7280'
              return (
                <div key={emp.admin_id} className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs w-5 font-mono" style={{ color: 'var(--text-faint)' }}>#{i+1}</span>
                  <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0"
                    style={{ background: tc }}>
                    {emp.employee_name?.[0]}
                  </div>
                  <span className="text-xs flex-1 truncate" style={{ color: 'var(--text)' }}>
                    {emp.employee_name}
                  </span>
                  <span className="text-sm font-light tabular-nums" style={{ color: tc }}>
                    {fmtScore(emp.total_score)}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </motion.div>
  )
}

// ── Annual pivot report ───────────────────────────────────────────────────
function AnnualReport({ monthData, year, kpis }) {
  const months = Object.keys(monthData).map(Number).sort((a,b) => a-b)
  if (months.length === 0) return null

  const empMap = {}
  months.forEach(m => {
    monthData[m].forEach(e => { empMap[e.admin_id] = e.employee_name })
  })
  const empList = Object.entries(empMap).sort((a,b) => a[1].localeCompare(b[1]))

  const exportExcel = () => {
    const rows = empList.map(([aid, name]) => {
      const row = { Employee: name }
      months.forEach(m => {
        const emp = monthData[m]?.find(e => e.admin_id === +aid)
        row[monthName(m)]           = emp ? +emp.total_score.toFixed(1) : null
        row[`${monthName(m)} Tier`] = emp?.tier?.grade ?? null
      })
      const vals = months.map(m => monthData[m]?.find(e=>e.admin_id===+aid)?.total_score).filter(v=>v!=null)
      row['Annual Avg'] = vals.length ? +(vals.reduce((a,b)=>a+b)/vals.length).toFixed(1) : null
      return row
    })
    const ws = XLSX.utils.json_to_sheet(rows)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, `MMC ${year}`)
    XLSX.writeFile(wb, `MMC_Annual_${year}.xlsx`)
    toast.success('Excel exported!')
  }

  const trendData = months.map(m => {
    const emps = monthData[m] || []
    return {
      month:  monthName(m).slice(0,3),
      avg:    emps.length ? +(emps.reduce((s,e)=>s+e.total_score,0)/emps.length).toFixed(1) : null,
      tierA:  emps.filter(e=>e.tier?.grade==='A').length,
    }
  })

  return (
    <motion.div initial={{ opacity:0, y:16 }} animate={{ opacity:1, y:0 }}
      className="card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor:'var(--border)' }}>
        <div>
          <p className="font-bold" style={{ color:'var(--text)' }}>Annual Report — {year}</p>
          <p className="text-xs" style={{ color:'var(--text-muted)' }}>
            {empList.length} employees · {months.length} months loaded · updates as you load more months
          </p>
        </div>
        <button onClick={exportExcel} className="btn btn-primary text-xs">
          <Download size={13} /> Export Excel
        </button>
      </div>

      {/* Pivot table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr style={{ background:'var(--bg)', borderBottom:'1px solid var(--border)' }}>
              <th className="px-4 py-3 text-left text-xs font-bold sticky left-0 z-10"
                style={{ color:'var(--text-faint)', background:'var(--bg)', minWidth:170 }}>EMPLOYEE</th>
              {months.map(m => (
                <th key={m} className="px-3 py-3 text-center text-xs font-bold"
                  style={{ color:'var(--text-faint)', minWidth:80 }}>
                  {monthName(m).slice(0,3).toUpperCase()}
                </th>
              ))}
              <th className="px-3 py-3 text-center text-xs font-bold"
                style={{ color:'#6366F1', minWidth:70 }}>AVG</th>
            </tr>
          </thead>
          <tbody>
            {empList.map(([aid, name]) => {
              const scores = months.map(m => monthData[m]?.find(e=>e.admin_id===+aid)?.total_score ?? null)
              const valid  = scores.filter(s => s !== null)
              const rowAvg = valid.length ? valid.reduce((a,b)=>a+b)/valid.length : null
              return (
                <tr key={aid} className="border-b transition-colors"
                  style={{ borderColor:'var(--border)' }}
                  onMouseEnter={e => e.currentTarget.style.background='var(--bg-hover)'}
                  onMouseLeave={e => e.currentTarget.style.background='transparent'}>
                  <td className="px-4 py-2.5 sticky left-0 z-10"
                    style={{ background:'var(--bg-card)' }}>
                    <div className="flex items-center gap-2.5">
                      <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
                        style={{ background:'#6366F1' }}>
                        {name[0]}
                      </div>
                      <span className="text-sm font-medium truncate max-w-[120px]" style={{ color:'var(--text)' }}>
                        {name}
                      </span>
                    </div>
                  </td>
                  {months.map(m => {
                    const emp = monthData[m]?.find(e => e.admin_id===+aid)
                    const sc  = emp?.total_score
                    const tc  = emp ? (TIER_COLOR[emp.tier?.grade] ?? '#6B7280') : null
                    return (
                      <td key={m} className="px-3 py-2.5 text-center">
                        {sc != null ? (
                          <div className="flex flex-col items-center gap-0.5">
                            <span className="text-sm font-light tabular-nums" style={{ color:tc }}>{sc.toFixed(1)}</span>
                            <span className="text-[10px] px-1.5 py-px rounded-full font-bold"
                              style={{ background:`${tc}18`, color:tc }}>{emp.tier?.grade}</span>
                          </div>
                        ) : <span style={{ color:'var(--text-faint)', fontSize:20 }}>·</span>}
                      </td>
                    )
                  })}
                  <td className="px-3 py-2.5 text-center border-l" style={{ borderColor:'var(--border)' }}>
                    {rowAvg != null
                      ? <span className="text-sm font-semibold tabular-nums" style={{ color:'#6366F1' }}>
                          {rowAvg.toFixed(1)}
                        </span>
                      : <span style={{ color:'var(--text-faint)', fontSize:20 }}>·</span>}
                  </td>
                </tr>
              )
            })}
            <tr style={{ borderTop:'2px solid var(--border)', background:'var(--bg)' }}>
              <td className="px-4 py-3 font-bold text-xs uppercase sticky left-0 z-10"
                style={{ color:'var(--text-muted)', background:'var(--bg)' }}>Team Average</td>
              {months.map(m => {
                const emps = monthData[m] || []
                const avg  = emps.length ? emps.reduce((s,e)=>s+e.total_score,0)/emps.length : null
                return (
                  <td key={m} className="px-3 py-3 text-center">
                    {avg != null
                      ? <span className="text-sm font-bold" style={{ color:'#6366F1' }}>{avg.toFixed(1)}</span>
                      : <span style={{ color:'var(--text-faint)' }}>—</span>}
                  </td>
                )
              })}
              <td />
            </tr>
          </tbody>
        </table>
      </div>

      {/* Trend chart */}
      {months.length >= 2 && (
        <div className="p-5 border-t" style={{ borderColor:'var(--border)' }}>
          <p className="font-semibold text-sm mb-4" style={{ color:'var(--text)' }}>Score Trend — {year}</p>
          <div style={{ height: 210 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData} margin={{ left:0, right:20, top:5, bottom:5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="month" tick={{ fill:'var(--text-muted)', fontSize:12 }} />
                <YAxis domain={[0,100]} tick={{ fill:'var(--text-muted)', fontSize:12 }} />
                <Tooltip contentStyle={{ background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:10, fontSize:13 }} />
                <Legend wrapperStyle={{ color:'var(--text-muted)', fontSize:12 }} />
                <Line type="monotone" dataKey="avg" name="Avg Score" stroke="#6366F1"
                  strokeWidth={2.5} dot={{ fill:'#6366F1', r:4, strokeWidth:0 }} connectNulls />
                <Line type="monotone" dataKey="tierA" name="Tier A Count" stroke="#10B981"
                  strokeWidth={2} strokeDasharray="4 3" dot={{ fill:'#10B981', r:3, strokeWidth:0 }} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </motion.div>
  )
}

// ── Main Preview page ─────────────────────────────────────────────────────
export default function Preview() {
  const [year,       setYear]      = useState(2026)
  const [kpis,       setKpis]      = useState([])
  const [monthData,  setMonthData] = useState({})   // month → employees[]
  const [status,     setStatus]    = useState({})   // month → 'loading'|'done'|'error'
  const [loadingAll, setLoadingAll]= useState(false)
  const stopAllRef = useRef(false)
  const navigate   = useNavigate()

  // Load KPI config once
  useEffect(() => {
    fetch('/api/kpis', { credentials:'include' })
      .then(r => r.json())
      .then(d => setKpis(d.kpis || []))
      .catch(() => {})
  }, [])

  // Reset when year changes
  useEffect(() => {
    setMonthData({})
    setStatus({})
  }, [year])

  // Load a single month
  const loadMonth = async (m) => {
    if (status[m] === 'loading' || status[m] === 'done') return

    setStatus(prev => ({ ...prev, [m]: 'loading' }))
    console.log(`[Preview] Loading ${m}/${year}`)

    try {
      const res = await fetch(`/api/scores?month=${m}&year=${year}`, { credentials:'include' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const emps = data.employees || []
      console.log(`[Preview] Got ${emps.length} employees for ${m}/${year}`)
      setMonthData(prev => ({ ...prev, [m]: emps }))
      setStatus(prev => ({ ...prev, [m]: 'done' }))
    } catch (err) {
      console.error(`[Preview] Error ${m}/${year}`, err)
      setStatus(prev => ({ ...prev, [m]: 'error' }))
      toast.error(`Failed to load ${monthName(m)}: ${err.message}`)
    }
  }

  // Load all months sequentially
  const loadAll = async () => {
    stopAllRef.current = false
    setLoadingAll(true)
    const nowM = new Date().getMonth() + 1
    const months = ALL_MONTHS.filter(m => !(year === new Date().getFullYear() && m > nowM))

    for (const m of months) {
      if (stopAllRef.current) break
      if (status[m] !== 'done') {
        await loadMonth(m)
      }
    }
    setLoadingAll(false)
  }

  const stopAll = () => {
    stopAllRef.current = true
    setLoadingAll(false)
  }

  const resetAll = () => {
    stopAllRef.current = true
    setLoadingAll(false)
    setMonthData({})
    setStatus({})
  }

  const nowM   = new Date().getMonth() + 1
  const nowY   = new Date().getFullYear()
  const visible = ALL_MONTHS.filter(m => !(year === nowY && m > nowM))
  const loaded  = Object.keys(monthData).map(Number).sort((a,b)=>a-b)
  const anyLoading = Object.values(status).includes('loading')

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-bold text-lg" style={{ color:'var(--text)' }}>Year Preview</h2>
          <p className="text-xs" style={{ color:'var(--text-muted)' }}>
            Click any month to load · cards appear instantly · annual report builds live
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <select value={year} onChange={e => setYear(+e.target.value)}
            disabled={anyLoading} className="form-input">
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          {!loadingAll ? (
            <button onClick={loadAll} disabled={anyLoading}
              className="btn btn-primary text-xs">
              ▶ Load All Sequentially
            </button>
          ) : (
            <button onClick={stopAll} className="btn text-xs"
              style={{ background:'#FEE2E2', color:'#DC2626', border:'1px solid #FECACA' }}>
              ■ Stop
            </button>
          )}
          {loaded.length > 0 && (
            <button onClick={resetAll} className="btn btn-secondary text-xs">
              <RotateCcw size={12} /> Reset
            </button>
          )}
        </div>
      </div>

      {/* Month selector grid */}
      <div className="card p-6">
        <p className="font-semibold text-sm mb-1" style={{ color:'var(--text)' }}>
          Select Months to Load
        </p>
        <p className="text-xs mb-5" style={{ color:'var(--text-muted)' }}>
          Click any month pill below · ✓ = loaded · ⟳ = computing (takes 2–3 min first time) · ⚡ = cached (instant)
        </p>
        <div className="flex flex-wrap gap-4 justify-start">
          {visible.map(m => (
            <MonthBtn
              key={m}
              month={m}
              status={status[m] ?? 'idle'}
              onClick={() => loadMonth(m)}
            />
          ))}
        </div>

        {/* Summary bar */}
        {loaded.length > 0 && (
          <div className="flex items-center gap-6 mt-6 pt-4 border-t flex-wrap"
            style={{ borderColor:'var(--border)' }}>
            <div className="text-center">
              <p className="text-2xl font-light" style={{ color:'#6366F1' }}>{loaded.length}</p>
              <p className="text-xs" style={{ color:'var(--text-faint)' }}>Months Loaded</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-light" style={{ color:'#10B981' }}>
                {Math.max(...loaded.map(m => monthData[m]?.length || 0))}
              </p>
              <p className="text-xs" style={{ color:'var(--text-faint)' }}>Max Employees</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-light" style={{ color:'#F59E0B' }}>
                {loaded.length > 0
                  ? (loaded.reduce((s,m) => {
                      const emps = monthData[m] || []
                      return s + (emps.length ? emps.reduce((a,e)=>a+e.total_score,0)/emps.length : 0)
                    }, 0) / loaded.length).toFixed(1)
                  : '—'}
              </p>
              <p className="text-xs" style={{ color:'var(--text-faint)' }}>YTD Avg Score</p>
            </div>
            {anyLoading && (
              <div className="flex items-center gap-2 ml-auto">
                <div className="w-4 h-4 rounded-full animate-spin"
                  style={{ border:'2px solid var(--border)', borderTopColor:'#6366F1' }} />
                <span className="text-xs" style={{ color:'var(--text-muted)' }}>Computing… please wait</span>
              </div>
            )}
          </div>
        )}

        {/* Empty hint */}
        {loaded.length === 0 && !anyLoading && (
          <div className="text-center py-6 border-t mt-5" style={{ borderColor:'var(--border)' }}>
            <p className="text-3xl mb-2">👆</p>
            <p className="font-medium mb-1" style={{ color:'var(--text)' }}>Click a month above to load it</p>
            <p className="text-xs" style={{ color:'var(--text-muted)' }}>
              Or click "Load All Sequentially" to load all months one by one
            </p>
            <div className="flex items-center justify-center gap-4 mt-4 text-xs" style={{ color:'var(--text-faint)' }}>
              <span>⚡ Cached = instant</span>
              <span>⟳ Fresh = ~2–3 min SQL queries</span>
              <span>✓ = Loaded</span>
            </div>
          </div>
        )}
      </div>

      {/* Month cards */}
      {loaded.length > 0 && (
        <div>
          <p className="font-semibold text-sm mb-3" style={{ color:'var(--text)' }}>
            Monthly Breakdown
            <span className="ml-2 text-xs font-normal px-2 py-0.5 rounded-full"
              style={{ background:'var(--bg-hover)', color:'var(--text-muted)' }}>
              {loaded.length} month{loaded.length !== 1 ? 's' : ''} loaded
            </span>
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {loaded.map(m => (
              <MonthCard key={m} month={m} year={year}
                employees={monthData[m] || []}
                kpis={kpis}
                onViewDashboard={(mo, yr) => navigate(`/dashboard?month=${mo}&year=${yr}`)}
              />
            ))}
            {/* Skeleton for currently loading months */}
            {Object.entries(status)
              .filter(([,s]) => s === 'loading')
              .map(([m]) => (
                <motion.div key={`skel-${m}`}
                  initial={{ opacity:0 }} animate={{ opacity:1 }}
                  className="card flex flex-col items-center justify-center gap-4 min-h-[280px]">
                  <div className="w-12 h-12 rounded-full animate-spin"
                    style={{ border:'3px solid var(--border)', borderTopColor:'#6366F1' }} />
                  <div className="text-center">
                    <p className="font-semibold text-sm" style={{ color:'var(--text)' }}>
                      Computing {monthName(+m)} {year}…
                    </p>
                    <p className="text-xs mt-1" style={{ color:'var(--text-muted)' }}>
                      SQL queries running · please wait
                    </p>
                    <div className="flex items-center justify-center gap-1.5 mt-3">
                      <Clock size={11} style={{ color:'var(--text-faint)' }} />
                      <span className="text-xs" style={{ color:'var(--text-faint)' }}>~2–3 minutes</span>
                    </div>
                  </div>
                </motion.div>
              ))}
          </div>
        </div>
      )}

      {/* Annual report */}
      {loaded.length > 0 && (
        <AnnualReport monthData={monthData} year={year} kpis={kpis} />
      )}
    </div>
  )
}
