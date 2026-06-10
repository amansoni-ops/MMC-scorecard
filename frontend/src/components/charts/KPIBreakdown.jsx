import { motion } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid } from 'recharts'
import { fmtPct, fmtScore } from '../../utils/formatters'

const COLORS = ['#0E7490','#10B981','#F59E0B','#8B5CF6','#EC4899']

export default function KPIBreakdown({ kpiBreakdown, kpis }) {
  if (!kpiBreakdown) return null
  const entries = Object.entries(kpiBreakdown)

  const chartData = entries.map(([key, kb], i) => ({
    name:     kb.name.split(' ').slice(0,2).join(' '),
    fullName: kb.name,
    success:  kb.success_ratio ?? 0,
    score:    kb.score ?? 0,
    fill:     COLORS[i % COLORS.length],
  }))

  return (
    <div className="space-y-6">
      {/* Horizontal bar chart */}
      <div className="glass p-6 rounded-2xl">
        <p className="font-semibold mb-1" style={{ color: 'var(--text)' }}>KPI Success Rates</p>
        <p className="text-xs mb-5" style={{ color: 'var(--text-muted)' }}>How well each KPI target was achieved this month</p>
        <ResponsiveContainer width="100%" height={Math.max(180, entries.length * 52)}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 50, top: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
            <XAxis type="number" domain={[0,100]} tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
              tickFormatter={v => `${v}%`} />
            <YAxis type="category" dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} width={110} />
            <Tooltip
              contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12 }}
              formatter={(v, n, p) => [fmtPct(v), p.payload.fullName]}
              labelFormatter={() => ''}
            />
            <Bar dataKey="success" radius={[0,8,8,0]} maxBarSize={26} animationDuration={900}
              label={{ position: 'right', fill: 'var(--text-muted)', fontSize: 11, formatter: v => `${v.toFixed(1)}%` }}>
              {chartData.map((d, i) => (
                <Cell key={i} fill={d.fill} style={{ filter: `drop-shadow(0 0 5px ${d.fill}50)` }} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* KPI detail cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {entries.map(([key, kb], i) => {
          const color   = COLORS[i % COLORS.length]
          const pct     = kb.success_ratio ?? 0
          const hasData = kb.denominator > 0
          return (
            <motion.div key={key}
              initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }}
              transition={{ delay: i * 0.07 }}
              className="glass glass-hover p-5 rounded-2xl"
              style={{ border: '1px solid var(--border)' }}>

              {/* Title + score */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 pr-2">
                  <p className="font-semibold text-sm leading-tight" style={{ color: 'var(--text)' }}>{kb.name}</p>
                  <p className="text-xs mt-1 leading-relaxed" style={{ color: 'var(--text-muted)' }}>{kb.description}</p>
                </div>
                <div className="text-right shrink-0">
                  {/* Score number — font-light, bigger */}
                  <p className="text-2xl font-light leading-none" style={{ color }}>
                    {hasData ? fmtPct(pct) : '—'}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-faint)' }}>success</p>
                </div>
              </div>

              {/* Progress bar */}
              <div className="h-2 rounded-full overflow-hidden mb-4" style={{ background: 'var(--border)' }}>
                <motion.div className="h-full rounded-full"
                  style={{ background: `linear-gradient(90deg, ${color}80, ${color})` }}
                  initial={{ width: 0 }}
                  animate={{ width: hasData ? `${pct}%` : 0 }}
                  transition={{ duration: 1, ease: 'easeOut', delay: i * 0.1 }}
                />
              </div>

              {/* Stats row */}
              <div className="flex justify-between items-center">
                <span className="text-xs" style={{ color: 'var(--text-faint)' }}>
                  {kb.numerator} / {kb.denominator}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Score:</span>
                  <span className="text-sm font-light" style={{ color }}>
                    {kb.score != null ? fmtScore(kb.score) : '—'}
                  </span>
                </div>
              </div>

              {/* Weight badge */}
              <div className="flex justify-between items-center mt-3 pt-3"
                style={{ borderTop: '1px solid var(--border-soft)' }}>
                <span className="text-xs" style={{ color: 'var(--text-faint)' }}>Weight</span>
                <span className="text-xs font-mono px-2 py-0.5 rounded-md border"
                  style={{ color, borderColor: `${color}40`, background: `${color}12` }}>
                  {kb.weight?.toFixed(1)}%
                </span>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
