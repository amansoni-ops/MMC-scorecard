import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { getCacheStatus, refreshCache } from '../api/scorecard'
import { useStore } from '../store/appStore'
import { RefreshCw, Database, Clock, Zap, Info } from 'lucide-react'
import toast from 'react-hot-toast'

const STEPS = [
  { icon: '🔐', title: 'Login',         desc: 'User logs in → backend immediately fires preload_async(current_month, current_year) in a background thread. UI navigates instantly without waiting.' },
  { icon: '💾', title: 'Cache Check',   desc: 'Every /api/scores request first checks the in-memory store. If an entry exists and is < 3 hours old, it returns immediately — no DB query.' },
  { icon: '⚙️',  title: 'Calculate',    desc: 'On cache miss: loads active KPIs from SQLite, normalizes weights, runs each KPI\'s SQL query against SQL Server, aggregates by employee, computes scores + tiers.' },
  { icon: '📦', title: 'Store',         desc: 'Result is stored in memory with a timestamp. Subsequent requests for the same month/year return instantly until TTL expires.' },
  { icon: '🔄', title: 'Auto Refresh',  desc: 'A background scheduler thread runs every 3 hours. It invalidates the current month\'s cache entry and recomputes it silently — users always get fresh data.' },
  { icon: '🗑️', title: 'Invalidation',  desc: 'Any KPI weight change or toggle immediately clears the entire cache so the next request reflects the updated configuration.' },
]

export default function CacheStatus() {
  const [status, setStatus]     = useState({})
  const [loading, setLoading]   = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const { selectedMonth: month, selectedYear: year } = useStore()

  const fetchStatus = async () => {
    setLoading(true)
    try { const r = await getCacheStatus(); setStatus(r.data) }
    catch { toast.error('Failed to load cache status') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchStatus() }, [])

  const handleRefresh = async (m, y) => {
    setRefreshing(true)
    try { await refreshCache(m, y); toast.success(`Cache refreshed for ${m}/${y}`); fetchStatus() }
    catch { toast.error('Refresh failed') }
    finally { setRefreshing(false) }
  }

  const entries = Object.entries(status)

  return (
    <div className="space-y-5 max-w-4xl">

      {/* Cache entries */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor:'var(--border)' }}>
          <div className="flex items-center gap-2.5">
            <Database size={17} style={{ color:'var(--primary)' }} />
            <p className="font-semibold text-sm" style={{ color:'var(--text)' }}>Live Cache Entries</p>
          </div>
          <button onClick={fetchStatus} className="btn btn-secondary text-xs">
            <RefreshCw size={12} className={loading?'animate-spin':''} /> Refresh Status
          </button>
        </div>

        {entries.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-3xl mb-2">📭</p>
            <p className="font-medium mb-1" style={{ color:'var(--text)' }}>No cache entries yet</p>
            <p className="text-sm" style={{ color:'var(--text-muted)' }}>Cache is populated when you view the dashboard</p>
          </div>
        ) : (
          <div className="divide-y" style={{ borderColor:'var(--border)' }}>
            {entries.map(([key, info]) => {
              const age = info.age_seconds
              const fresh = age < 10800
              const mins = Math.floor(age / 60)
              return (
                <motion.div key={key} initial={{ opacity:0 }} animate={{ opacity:1 }}
                  className="flex items-center justify-between px-5 py-4">
                  <div className="flex items-center gap-4">
                    <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Database size={16} style={{ color:'var(--primary)' }} />
                    </div>
                    <div>
                      <p className="font-medium text-sm" style={{ color:'var(--text)' }}>
                        Period: {key.replace(/[()]/g,'').replace(',','/')}
                      </p>
                      <p className="text-xs mt-0.5" style={{ color:'var(--text-muted)' }}>
                        <Clock size={11} className="inline mr-1" />
                        Cached at {info.cached_at?.slice(11,16)} · {mins < 60 ? `${mins}m ago` : `${Math.floor(mins/60)}h ago`}
                        &nbsp;·&nbsp; {info.employees} employees
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`badge ${fresh ? 'badge-green' : 'badge-amber'}`}>
                      {fresh ? '● Fresh' : '⚠ Stale'}
                    </span>
                    <button onClick={() => {
                      const [m,y] = key.replace(/[()]/g,'').split(',').map(Number)
                      handleRefresh(m, y)
                    }} className="btn btn-secondary text-xs" disabled={refreshing}>
                      <RefreshCw size={11} className={refreshing?'animate-spin':''} /> Refresh
                    </button>
                  </div>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>

      {/* How it works */}
      <div className="card overflow-hidden">
        <div className="flex items-center gap-2.5 px-5 py-4 border-b" style={{ borderColor:'var(--border)' }}>
          <Info size={17} style={{ color:'var(--primary)' }} />
          <p className="font-semibold text-sm" style={{ color:'var(--text)' }}>How Caching Works</p>
        </div>
        <div className="p-5 space-y-0">
          {STEPS.map((s, i) => (
            <div key={i} className="flex gap-4 pb-5 last:pb-0 relative">
              {/* Connector line */}
              {i < STEPS.length - 1 && (
                <div className="absolute left-5 top-10 bottom-0 w-px" style={{ background:'var(--border)' }} />
              )}
              <div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg shrink-0 z-10"
                style={{ background:'var(--bg-hover)' }}>
                {s.icon}
              </div>
              <div className="pt-1.5">
                <p className="font-semibold text-sm mb-1" style={{ color:'var(--text)' }}>
                  <span className="text-xs font-bold mr-2 px-1.5 py-0.5 rounded"
                    style={{ background:'var(--primary)', color:'#fff' }}>{i+1}</span>
                  {s.title}
                </p>
                <p className="text-sm leading-relaxed" style={{ color:'var(--text-muted)' }}>{s.desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* TTL info */}
        <div className="mx-5 mb-5 rounded-xl p-4 flex items-start gap-3"
          style={{ background:'rgba(99,102,241,0.06)', border:'1px solid rgba(99,102,241,0.15)' }}>
          <Zap size={16} className="mt-0.5 shrink-0" style={{ color:'var(--primary)' }} />
          <div>
            <p className="text-sm font-semibold mb-1" style={{ color:'var(--text)' }}>TTL = 3 hours</p>
            <p className="text-xs leading-relaxed" style={{ color:'var(--text-muted)' }}>
              Cache entries expire after 3 hours. The background scheduler automatically recomputes the current month every 3 hours.
              Changing KPI weights or toggling a KPI instantly invalidates all cache entries so scores always reflect
              the latest configuration.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
