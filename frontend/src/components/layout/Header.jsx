import { useState, useEffect } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import { Search, Bell, RefreshCw, ChevronRight } from 'lucide-react'
import { useStore } from '../../store/appStore'
import { refreshCache } from '../../api/scorecard'
import toast from 'react-hot-toast'
import { monthName } from '../../utils/formatters'

const PAGE_META = {
  '/dashboard':  { parent: null,       label: 'Dashboard'     },
  '/reports':    { parent: 'Dashboard', label: 'Score Reports' },
  '/comparison': { parent: 'Dashboard', label: 'Comparison'    },
  '/cache':      { parent: 'System',    label: 'Cache Status'  },
}

function QuickSearch({ employees, navigate }) {
  const [open, setOpen]   = useState(false)
  const [query, setQuery] = useState('')
  const { selectedMonth: month, selectedYear: year } = useStore()

  const results = query.length >= 2
    ? employees.filter(e => e.employee_name.toLowerCase().includes(query.toLowerCase())).slice(0, 6)
    : []

  return (
    <div className="relative">
      <div className="flex items-center gap-2 form-input w-52 cursor-pointer"
        onClick={() => setOpen(true)} style={{ padding: '6px 10px' }}>
        <Search size={14} style={{ color: 'var(--text-faint)' }} />
        <span style={{ color: 'var(--text-faint)', fontSize: 13 }}>Quick search…</span>
        <span className="ml-auto text-xs px-1.5 py-0.5 rounded"
          style={{ background: 'var(--bg-hover)', color: 'var(--text-faint)' }}>⌘K</span>
      </div>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => { setOpen(false); setQuery('') }} />
          <div className="absolute top-10 left-0 z-50 w-72 card p-2" style={{ boxShadow: 'var(--shadow-lg)' }}>
            <input autoFocus value={query} onChange={e => setQuery(e.target.value)}
              placeholder="Search employee name…"
              className="form-input w-full mb-2" />
            {results.length > 0 ? results.map(e => (
              <button key={e.admin_id}
                onClick={() => { navigate(`/employee/${e.admin_id}?month=${month}&year=${year}`); setOpen(false); setQuery('') }}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-colors"
                style={{ fontSize: 13 }}
                onMouseEnter={el => el.currentTarget.style.background='var(--bg-hover)'}
                onMouseLeave={el => el.currentTarget.style.background='transparent'}>
                <span style={{ color: 'var(--text)' }}>{e.employee_name}</span>
                <span className={`badge text-xs tier-${e.tier?.grade?.toLowerCase()}`}>
                  {e.tier?.grade}  {e.total_score?.toFixed(1)}
                </span>
              </button>
            )) : query.length >= 2 ? (
              <p className="text-center py-4 text-sm" style={{ color: 'var(--text-faint)' }}>No results</p>
            ) : (
              <p className="text-center py-4 text-sm" style={{ color: 'var(--text-faint)' }}>Type to search employees</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ── DB Status badge (ONLY change from original) ────────────────────────────
function DBStatusBadge() {
  const [status, setStatus] = useState({ sqlite: null, sqlserver: null })

  const check = () => {
    fetch('/api/health/db', { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => setStatus({ sqlite: d.sqlite, sqlserver: d.sqlserver }))
      .catch(() => setStatus({ sqlite: false, sqlserver: false }))
  }

  useEffect(() => {
    check()
    const t = setInterval(check, 30000)
    return () => clearInterval(t)
  }, [])

  const bothOk  = status.sqlite && status.sqlserver
  const loading = status.sqlite === null && status.sqlserver === null

  const label = loading      ? 'Checking…'
    : bothOk                 ? 'Connected'
    : !status.sqlite         ? 'Local DB Error'
    : !status.sqlserver      ? 'SQL Server Error'
    :                          'DB Error'

  return (
    <div
      title={`Local DB: ${status.sqlite ? 'OK' : '…'} | SQL Server: ${status.sqlserver ? 'OK' : 'Error'}`}
      className={`badge ${bothOk ? 'badge-green' : loading ? '' : 'badge-red'} flex items-center gap-1.5`}
      style={!bothOk && !loading ? {
        background: 'rgba(239,68,68,0.12)',
        color: '#DC2626',
      } : {}}>
      <span className="w-1.5 h-1.5 rounded-full inline-block"
        style={{
          background: loading ? '#94A3B8' : bothOk ? '#10B981' : '#EF4444',
          boxShadow:  bothOk ? '0 0 5px rgba(16,185,129,0.5)' : 'none',
        }}/>
      {label}
    </div>
  )
}

export default function Header() {
  const location     = useLocation()
  const navigate     = useNavigate()
  const { user, employees, selectedMonth: month, selectedYear: year } = useStore()
  const [refreshing, setRefreshing] = useState(false)

  const meta = Object.entries(PAGE_META).find(([k]) => location.pathname.startsWith(k))?.[1]
    ?? { parent: null, label: 'Page' }

  const handleRefresh = async () => {
    setRefreshing(true)
    try { await refreshCache(month, year); toast.success('Cache refreshed') }
    catch { toast.error('Refresh failed') }
    finally { setTimeout(() => setRefreshing(false), 1000) }
  }

  useEffect(() => {
    const h = e => { if ((e.metaKey || e.ctrlKey) && e.key === 'k') e.preventDefault() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])

  return (
    <header className="flex items-center justify-between px-5 border-b shrink-0"
      style={{ background: 'var(--bg-header)', borderColor: 'var(--border)', height: 56, zIndex: 10 }}>

      <div>
        <div className="flex items-center gap-1.5 mb-0.5" style={{ fontSize: 12, color: 'var(--text-faint)' }}>
          <span>MMC Scorecard</span>
          {meta.parent && (
            <>
              <ChevronRight size={12} />
              <span>{meta.parent}</span>
            </>
          )}
        </div>
        <h1 className="font-semibold text-base leading-none" style={{ color: 'var(--text)' }}>{meta.label}</h1>
      </div>

      <div className="flex items-center gap-3">
        <QuickSearch employees={employees} navigate={navigate} />

        <DBStatusBadge />

        <button onClick={handleRefresh}
          className="btn btn-secondary h-8 w-8 p-0 flex items-center justify-center"
          title="Refresh cache">
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
        </button>

        <button className="btn btn-secondary h-8 w-8 p-0 flex items-center justify-center relative">
          <Bell size={14} />
        </button>

        <div className="flex items-center gap-2 pl-2 border-l" style={{ borderColor: 'var(--border)' }}>
          <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-white text-xs font-bold">
            {user?.username?.[0]?.toUpperCase()}
          </div>
          <div className="leading-tight">
            <p className="text-xs font-semibold capitalize" style={{ color: 'var(--text)' }}>{user?.username}</p>
            <p className="text-xs capitalize" style={{ color: 'var(--text-faint)' }}>{user?.role}</p>
          </div>
        </div>
      </div>
    </header>
  )
}
