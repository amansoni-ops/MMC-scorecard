import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Power, Save } from 'lucide-react'
import toast from 'react-hot-toast'

const KPI_COLORS = ['#6366F1', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']

export default function KPIWeightManager({ onClose }) {
  const [kpis,   setKPIs]   = useState([])
  const [saving, setSaving] = useState(false)
  const isDark = document.documentElement.classList.contains('dark') ||
                 document.documentElement.getAttribute('data-theme') === 'dark'

  useEffect(() => {
    fetch('/api/kpis', { credentials: 'include' })
      .then(r => r.json())
      .then(d => setKPIs(d.kpis ?? []))
      .catch(() => toast.error('Could not load KPIs'))
  }, [])

  const active   = kpis.filter(k => k.is_active)
  const rawTotal = active.reduce((s, k) => s + (k.raw_weight || 0), 0)

  const toggle    = (key) => setKPIs(p => p.map(k => k.key === key ? { ...k, is_active: !k.is_active } : k))
  const setWeight = (key, val) => setKPIs(p => p.map(k => k.key === key ? { ...k, raw_weight: Math.max(0, Math.min(100, +val || 0)) } : k))
  const effPct    = (k) => rawTotal > 0 ? ((k.raw_weight || 0) / rawTotal * 100).toFixed(1) : '0'

  const segments = active.map((k, i) => ({
    pct:   rawTotal > 0 ? (k.raw_weight / rawTotal) * 100 : 0,
    color: KPI_COLORS[i % KPI_COLORS.length],
  }))

  const save = async () => {
    setSaving(true)
    try {
      const res = await fetch('/api/kpis', {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kpis }),
      })
      if (!res.ok) throw new Error(res.status)
      toast.success('Saved! Recalculating scores…')
      onClose()
    } catch (e) {
      toast.error(`Save failed: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <motion.div className="fixed inset-0 z-50 flex items-center justify-center"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>

      {/* Overlay — semi-transparent so dashboard is visible behind */}
      <div className="absolute inset-0"
        style={{ background: 'rgba(0,0,0,0.28)', backdropFilter: 'blur(2px)' }}
        onClick={onClose}/>

      {/* Modal — frosted glass: readable but slightly transparent */}
      <motion.div className="relative flex flex-col"
        initial={{ scale: 0.93, y: 12 }} animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.93, y: 12 }}
        style={{
          width: 540,
          maxHeight: '88vh',
          /* Light mode: white at 96% opacity */
          background: isDark
            ? 'rgba(30, 30, 30, 0.96)'
            : 'rgba(255, 255, 255, 0.96)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: isDark
            ? '1px solid rgba(80,80,80,0.5)'
            : '1px solid rgba(255,255,255,0.8)',
          borderRadius: 20,
          boxShadow: '0 20px 60px rgba(0,0,0,0.22), 0 2px 12px rgba(0,0,0,0.12)',
          overflow: 'hidden',
        }}>

        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-6 pb-4 shrink-0">
          <div>
            <p className="font-bold text-base" style={{ color: 'var(--text)' }}>KPI Configuration</p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              Weights auto-normalize to 100% across active KPIs
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg transition-colors"
            style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)' }}>
            <X size={15}/>
          </button>
        </div>

        {/* Weight bar */}
        <div className="px-6 pb-4 shrink-0">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Raw weight total (active KPIs)
            </p>
            <span className="text-xs font-bold"
              style={{ color: rawTotal === 100 ? '#10B981' : '#6366F1' }}>
              {rawTotal}
            </span>
          </div>
          <div className="flex h-2.5 rounded-full overflow-hidden gap-0.5"
            style={{ background: 'var(--border)' }}>
            {segments.map((s, i) => (
              <div key={i} className="h-full rounded-full transition-all"
                style={{ width: `${s.pct}%`, background: s.color, minWidth: s.pct > 0 ? 4 : 0 }}/>
            ))}
          </div>
        </div>

        {/* KPI list — scrollable */}
        <div className="flex-1 overflow-y-auto px-6 space-y-3 pb-4">
          {kpis.map((k, i) => {
            const isActive = k.is_active
            const color    = KPI_COLORS[i % KPI_COLORS.length]
            return (
              <div key={k.key}
                className="rounded-xl p-4 border transition-all"
                style={{
                  background:   isActive
                    ? (isDark ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.9)')
                    : (isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)'),
                  borderColor:  isActive ? `${color}45` : 'var(--border)',
                  opacity:      isActive ? 1 : 0.6,
                }}>
                <div className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>{k.name}</p>
                      {isActive ? (
                        <span className="text-xs px-2 py-0.5 rounded-full font-bold"
                          style={{ background: `${color}18`, color }}>
                          {effPct(k)}% effective
                        </span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 rounded-full"
                          style={{ background: 'var(--border)', color: 'var(--text-faint)' }}>
                          Disabled
                        </span>
                      )}
                    </div>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{k.description}</p>
                  </div>

                  {isActive ? (
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Weight</span>
                      <input
                        type="number" min={0} max={100} value={k.raw_weight ?? 0}
                        onChange={e => setWeight(k.key, e.target.value)}
                        className="form-input text-center tabular-nums"
                        style={{ width: 58, height: 32, padding: '0 6px', fontSize: 13 }}/>
                    </div>
                  ) : (
                    <span className="text-xs tabular-nums shrink-0 w-10 text-right"
                      style={{ color: 'var(--text-faint)' }}>0</span>
                  )}

                  <button onClick={() => toggle(k.key)}
                    className="p-1.5 rounded-lg transition-colors shrink-0"
                    style={{
                      background: isActive ? `${color}18` : 'var(--border)',
                      color:      isActive ? color : 'var(--text-faint)',
                    }}>
                    <Power size={14}/>
                  </button>
                </div>

                {isActive && (
                  <div className="mt-3 h-1 rounded-full overflow-hidden"
                    style={{ background: 'var(--border)' }}>
                    <div className="h-full rounded-full transition-all"
                      style={{ width: `${effPct(k)}%`, background: color }}/>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex gap-3 shrink-0"
          style={{
            borderColor: 'var(--border)',
            background: isDark ? 'rgba(30,30,30,0.8)' : 'rgba(255,255,255,0.8)',
          }}>
          <button onClick={onClose} className="btn btn-secondary flex-1">Cancel</button>
          <button onClick={save} disabled={saving} className="btn btn-primary flex-1">
            <Save size={13}/>
            {saving ? 'Saving…' : 'Save & Apply'}
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}