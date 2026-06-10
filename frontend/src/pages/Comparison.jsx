import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer,
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { MONTHS, YEARS, fmtScore, monthName } from '../utils/formatters'
import toast from 'react-hot-toast'

const TIER_COLOR = { A: '#10B981', B: '#F59E0B', C: '#EF4444' }
const C1 = '#6366F1', C2 = '#F59E0B'

export default function Comparison() {
  // const [month,  setMonth]  = useState(3)
  // const [year,   setYear]   = useState(2026)
  const { selectedMonth: month, selectedYear: year,
        setSelectedMonth: setMonth, setSelectedYear: setYear } = useStore()
  const [employees, setEmps] = useState([])
  const [empA,   setEmpA]   = useState(null)
  const [empB,   setEmpB]   = useState(null)
  const [dataA,  setDataA]  = useState(null)
  const [dataB,  setDataB]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [lA, setLA] = useState(false)
  const [lB, setLB] = useState(false)

  // Fetch employee list when month/year changes
  useEffect(() => {
    setLoading(true)
    setDataA(null); setDataB(null); setEmpA(null); setEmpB(null)
    fetch(`/api/scores?month=${month}&year=${year}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => {
        const sorted = [...(d.employees || [])].sort((a, b) =>
          (a.employee_name || '').localeCompare(b.employee_name || ''))
        setEmps(sorted)
        setLoading(false)
      })
      .catch(e => { toast.error(`Load failed: ${e}`); setLoading(false) })
  }, [month, year])

  // Fetch detail for employee A
  useEffect(() => {
    if (!empA) { setDataA(null); return }
    setLA(true)
    fetch(`/api/scores/${empA}?month=${month}&year=${year}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => { setDataA(d); setLA(false) })
      .catch(() => setLA(false))
  }, [empA, month, year])

  // Fetch detail for employee B
  useEffect(() => {
    if (!empB) { setDataB(null); return }
    setLB(true)
    fetch(`/api/scores/${empB}?month=${month}&year=${year}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => { setDataB(d); setLB(false) })
      .catch(() => setLB(false))
  }, [empB, month, year])

  // Build comparison bar data
  const kpiKeys  = dataA ? Object.keys(dataA.kpi_breakdown) : dataB ? Object.keys(dataB.kpi_breakdown) : []
  const barData  = kpiKeys.map(key => {
    const kA = dataA?.kpi_breakdown?.[key]
    const kB = dataB?.kpi_breakdown?.[key]
    return {
      name: (kA || kB)?.name?.split(' ').slice(0, 2).join(' ') || key,
      A:    +(kA?.success_ratio ?? 0).toFixed(1),
      B:    +(kB?.success_ratio ?? 0).toFixed(1),
    }
  })

  const EmpSelector = ({ label, value, onChange, color, exclude }) => (
    <div className="flex-1 min-w-[200px]">
      <label className="block text-xs font-semibold mb-1.5"
        style={{ color: 'var(--text-faint)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        {label}
      </label>
      <select value={value || ''} onChange={e => onChange(e.target.value || null)}
        className="form-input w-full"
        style={{ borderColor: value ? color : 'var(--border)' }}>
        <option value="">— Select employee —</option>
        {employees.filter(e => String(e.admin_id) !== String(exclude)).map(e => (
          <option key={e.admin_id} value={e.admin_id}>{e.employee_name}</option>
        ))}
      </select>
    </div>
  )

  const EmpCard = ({ data, loading, color }) => {
    if (loading) return (
      <div className="flex-1 card p-5 flex items-center justify-center" style={{ minHeight: 200 }}>
        <div className="w-8 h-8 rounded-full animate-spin"
          style={{ border: '2px solid var(--border)', borderTopColor: color }}/>
      </div>
    )
    if (!data) return (
      <div className="flex-1 card p-5 flex items-center justify-center" style={{ minHeight: 200 }}>
        <p className="text-sm" style={{ color: 'var(--text-faint)' }}>Select an employee above</p>
      </div>
    )
    const tc = TIER_COLOR[data.tier?.grade] ?? color
    return (
      <div className="flex-1 card p-5" style={{ borderColor: `${color}40`, borderWidth: 2 }}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center text-base font-bold text-white"
            style={{ background: tc }}>{data.employee_name?.[0]}</div>
          <div>
            <p className="font-bold" style={{ color: 'var(--text)' }}>{data.employee_name}</p>
            <span className="text-xs px-2 py-0.5 rounded-full font-bold"
              style={{ background: `${tc}18`, color: tc }}>
              Tier {data.tier?.grade}
            </span>
          </div>
          <div className="ml-auto text-right">
            <p className="text-3xl font-light" style={{ color: tc }}>{fmtScore(data.total_score)}</p>
            <p className="text-xs" style={{ color: 'var(--text-faint)' }}>Total Score</p>
          </div>
        </div>
        <div className="space-y-2">
          {Object.entries(data.kpi_breakdown || {}).map(([key, kpi]) => (
            <div key={key}>
              <div className="flex justify-between text-xs mb-0.5">
                <span style={{ color: 'var(--text-muted)' }}>{kpi.name}</span>
                <span className="font-medium" style={{ color }}>
                  {kpi.success_ratio !== null ? `${kpi.success_ratio.toFixed(1)}%` : 'N/A'}
                </span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                <div className="h-full rounded-full transition-all"
                  style={{ width: `${kpi.success_ratio ?? 0}%`, background: color }}/>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-bold text-lg" style={{ color: 'var(--text)' }}>Employee Comparison</h2>
        <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Select two employees to compare their KPI performance side by side
        </p>
      </div>

      {/* Controls */}
      <div className="card p-4 flex items-end gap-3 flex-wrap">
        <div>
          <label className="block text-xs font-semibold mb-1.5"
            style={{ color: 'var(--text-faint)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            Month
          </label>
          <select value={month} onChange={e => setMonth(+e.target.value)} className="form-input">
            {MONTHS.map(m => <option key={m.value} value={m.value}>{m.full}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold mb-1.5"
            style={{ color: 'var(--text-faint)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            Year
          </label>
          <select value={year} onChange={e => setYear(+e.target.value)} className="form-input">
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <EmpSelector label="Employee A" value={empA} onChange={setEmpA} color={C1} exclude={empB}/>
        <EmpSelector label="Employee B" value={empB} onChange={setEmpB} color={C2} exclude={empA}/>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="w-10 h-10 rounded-full animate-spin"
            style={{ border: '3px solid var(--border)', borderTopColor: '#6366F1' }}/>
        </div>
      )}

      {!loading && (
        <>
          {/* Side-by-side cards */}
          <div className="flex gap-4 flex-wrap">
            <EmpCard data={dataA} loading={lA} color={C1}/>
            {/* VS divider */}
            <div className="flex items-center justify-center w-8 shrink-0">
              <div className="text-sm font-bold py-2 px-1 rounded-lg"
                style={{ color: 'var(--text-faint)', background: 'var(--bg-hover)', writingMode: 'vertical-rl' }}>
                VS
              </div>
            </div>
            <EmpCard data={dataB} loading={lB} color={C2}/>
          </div>

          {/* Grouped bar chart */}
          {(dataA || dataB) && barData.length > 0 && (
            <div className="card p-5">
              <p className="font-semibold text-sm mb-4" style={{ color: 'var(--text)' }}>
                KPI Comparison
              </p>
              <div style={{ height: 240 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} margin={{ left: 0, right: 20, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)"/>
                    <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 12 }}/>
                    <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 12 }}/>
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, fontSize: 13 }}
                      formatter={(v, n) => [`${v}%`, n === 'A' ? (dataA?.employee_name || 'A') : (dataB?.employee_name || 'B')]}/>
                    {dataA && <Bar dataKey="A" fill={C1} radius={[4, 4, 0, 0]} maxBarSize={28} name="A"/>}
                    {dataB && <Bar dataKey="B" fill={C2} radius={[4, 4, 0, 0]} maxBarSize={28} name="B"/>}
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Score difference */}
              {dataA && dataB && (
                <div className="mt-4 p-4 rounded-xl" style={{ background: 'var(--bg-hover)' }}>
                  <div className="flex items-center justify-around flex-wrap gap-4">
                    <div className="text-center">
                      <p className="text-2xl font-light" style={{ color: C1 }}>
                        {fmtScore(dataA.total_score)}
                      </p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{dataA.employee_name}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xl font-bold"
                        style={{ color: dataA.total_score >= dataB.total_score ? C1 : C2 }}>
                        {dataA.total_score >= dataB.total_score ? '+' : ''}
                        {(dataA.total_score - dataB.total_score).toFixed(1)} pts
                      </p>
                      <p className="text-xs" style={{ color: 'var(--text-faint)' }}>Difference</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-light" style={{ color: C2 }}>
                        {fmtScore(dataB.total_score)}
                      </p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{dataB.employee_name}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {!empA && !empB && (
            <div className="text-center py-16">
              <p className="text-4xl mb-3">👥</p>
              <p className="font-semibold mb-1" style={{ color: 'var(--text)' }}>
                Select two employees to compare
              </p>
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                Use the dropdowns above to choose employees from {monthName(month)} {year}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
