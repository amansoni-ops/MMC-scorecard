import { useEffect, useState } from 'react'
import { Download, RefreshCw, ChevronUp, ChevronDown } from 'lucide-react'
import { MONTHS, YEARS, fmtScore, monthName } from '../utils/formatters'
import toast from 'react-hot-toast'

const TIER_COLOR = { A: '#10B981', B: '#F59E0B', C: '#EF4444' }

export default function Reports() {
  // const [month,   setMonth]   = useState(3)
  // const [year,    setYear]    = useState(2026)
  const { selectedMonth: month, selectedYear: year,
        setSelectedMonth: setMonth, setSelectedYear: setYear } = useStore()
  const [rows,    setRows]    = useState([])
  const [loading, setLoading] = useState(false)
  const [sortCol, setSortCol] = useState('score')
  const [sortDir, setSortDir] = useState('desc')

  const load = (m, y) => {
    setLoading(true)
    fetch(`/api/scores?month=${m}&year=${y}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => {
        setRows(d.employees ?? [])
        setLoading(false)
        if (!(d.employees ?? []).length) toast('No data for this month.')
      })
      .catch(e => { toast.error(`Load failed: ${e}`); setLoading(false) })
  }

  useEffect(() => { load(month, year) }, [month, year])

  const sort = (col) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('desc') }
  }

  const sorted = [...rows].sort((a, b) => {
    let va, vb
    if (sortCol === 'name') { va = a.employee_name || ''; vb = b.employee_name || '' }
    else if (sortCol === 'tier') { va = a.tier?.grade || 'Z'; vb = b.tier?.grade || 'Z' }
    else { va = a.total_score ?? 0; vb = b.total_score ?? 0 }
    if (va < vb) return sortDir === 'asc' ? -1 : 1
    if (va > vb) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  const exportCSV = () => {
    const kpiKeys = rows[0] ? Object.keys(rows[0].kpi_breakdown || {}) : []
    const hdr = ['#', 'Name', 'Tier', 'Score', ...kpiKeys.map(k => rows[0].kpi_breakdown[k].name)]
    const lines = [hdr.join(',')]
    sorted.forEach((emp, i) => {
      const vals = [
        i + 1, `"${emp.employee_name}"`, emp.tier?.grade ?? '',
        emp.total_score ?? 0,
        ...kpiKeys.map(k => emp.kpi_breakdown?.[k]?.success_ratio?.toFixed(1) ?? ''),
      ]
      lines.push(vals.join(','))
    })
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `scorecard_${year}_${String(month).padStart(2,'0')}.csv`
    a.click()
  }

  const kpiKeys = rows[0] ? Object.keys(rows[0].kpi_breakdown || {}) : []

  const SortIcon = ({ col }) => {
    if (sortCol !== col) return <ChevronUp size={11} style={{ opacity: 0.3 }}/>
    return sortDir === 'asc' ? <ChevronUp size={11}/> : <ChevronDown size={11}/>
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-bold text-lg" style={{ color: 'var(--text)' }}>Score Reports</h2>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            All employees · {monthName(month)} {year}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <select value={month} onChange={e => setMonth(+e.target.value)} className="form-input">
            {MONTHS.map(m => <option key={m.value} value={m.value}>{m.full}</option>)}
          </select>
          <select value={year} onChange={e => setYear(+e.target.value)} className="form-input">
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <button onClick={() => load(month, year)} className="btn btn-secondary" disabled={loading}>
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''}/>
            {loading ? 'Loading…' : 'Refresh'}
          </button>
          <button onClick={exportCSV} className="btn btn-primary" disabled={!rows.length}>
            <Download size={13}/> Export CSV
          </button>
        </div>
      </div>

      <div className="card overflow-hidden">
        {/* Summary strip */}
        {rows.length > 0 && (
          <div className="grid grid-cols-4 divide-x border-b"
            style={{ borderColor: 'var(--border)', divideColor: 'var(--border)' }}>
            {[
              { label: 'Total Employees', value: rows.length, color: '#6366F1' },
              { label: 'Tier A', value: rows.filter(r => r.tier?.grade === 'A').length, color: '#10B981' },
              { label: 'Tier B', value: rows.filter(r => r.tier?.grade === 'B').length, color: '#F59E0B' },
              { label: 'Tier C', value: rows.filter(r => r.tier?.grade === 'C').length, color: '#EF4444' },
            ].map(s => (
              <div key={s.label} className="p-4 text-center">
                <p className="text-2xl font-light" style={{ color: s.color }}>{s.value}</p>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{s.label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <div className="w-10 h-10 rounded-full animate-spin"
              style={{ border: '3px solid var(--border)', borderTopColor: '#6366F1' }}/>
            <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>
              Loading {monthName(month)} {year}…
            </p>
            <p className="text-xs" style={{ color: 'var(--text-faint)' }}>
              First load takes 2–3 min · Cached after that
            </p>
          </div>
        )}

        {/* Empty */}
        {!loading && rows.length === 0 && (
          <div className="text-center py-16">
            <p className="text-3xl mb-3">📋</p>
            <p className="font-semibold" style={{ color: 'var(--text)' }}>
              No data for {monthName(month)} {year}
            </p>
            <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
              Try loading from the Dashboard first
            </p>
          </div>
        )}

        {/* Table */}
        {!loading && sorted.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--bg)', borderBottom: '1px solid var(--border)' }}>
                  <th className="px-4 py-3 text-left text-xs font-semibold" style={{ color: 'var(--text-faint)' }}>
                    #
                  </th>
                  <th className="px-4 py-3 text-left cursor-pointer select-none"
                    onClick={() => sort('name')}>
                    <span className="flex items-center gap-1 text-xs font-semibold" style={{ color: 'var(--text-faint)' }}>
                      EMPLOYEE <SortIcon col="name"/>
                    </span>
                  </th>
                  <th className="px-4 py-3 text-left cursor-pointer select-none"
                    onClick={() => sort('tier')}>
                    <span className="flex items-center gap-1 text-xs font-semibold" style={{ color: 'var(--text-faint)' }}>
                      TIER <SortIcon col="tier"/>
                    </span>
                  </th>
                  {kpiKeys.map(k => (
                    <th key={k} className="px-4 py-3 text-left text-xs font-semibold"
                      style={{ color: 'var(--text-faint)' }}>
                      {(rows[0]?.kpi_breakdown?.[k]?.name || k).split(' ').slice(0, 2).join(' ').toUpperCase()}
                    </th>
                  ))}
                  <th className="px-4 py-3 text-right cursor-pointer select-none"
                    onClick={() => sort('score')}>
                    <span className="flex items-center justify-end gap-1 text-xs font-semibold" style={{ color: 'var(--text-faint)' }}>
                      SCORE <SortIcon col="score"/>
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((emp, i) => {
                  const tc = TIER_COLOR[emp.tier?.grade] ?? '#6366F1'
                  return (
                    <tr key={emp.admin_id} className="border-b"
                      style={{ borderColor: 'var(--border)' }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                      <td className="px-4 py-3 text-xs font-mono" style={{ color: 'var(--text-faint)' }}>{i + 1}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2.5">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
                            style={{ background: tc }}>
                            {emp.employee_name?.[0]}
                          </div>
                          <span className="font-medium" style={{ color: 'var(--text)' }}>
                            {emp.employee_name}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs font-bold px-2 py-0.5 rounded-full"
                          style={{ background: `${tc}18`, color: tc }}>
                          {emp.tier?.grade}
                        </span>
                      </td>
                      {kpiKeys.map(k => {
                        const kpi = emp.kpi_breakdown?.[k]
                        const pct = kpi?.success_ratio
                        return (
                          <td key={k} className="px-4 py-3">
                            <div className="flex items-center gap-2 min-w-[100px]">
                              <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                                <div className="h-full rounded-full" style={{ width: `${pct ?? 0}%`, background: '#6366F1' }}/>
                              </div>
                              <span className="text-xs tabular-nums w-9 text-right" style={{ color: 'var(--text-muted)' }}>
                                {pct !== null && pct !== undefined ? `${pct.toFixed(1)}%` : '—'}
                              </span>
                            </div>
                          </td>
                        )
                      })}
                      <td className="px-4 py-3 text-right">
                        <span className="text-xl font-light tabular-nums" style={{ color: tc }}>
                          {fmtScore(emp.total_score)}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
