import { motion } from 'framer-motion'
import { fmtScore, fmtPct } from '../../utils/formatters'

const TIER_COLOR = { A: '#10B981', B: '#F59E0B', C: '#EF4444' }
const TIER_LABEL = { A: 'High Performer', B: 'Consistent', C: 'Needs Improvement' }

export default function EmployeeCard({ emp, kpis = [] }) {
  const tc     = TIER_COLOR[emp.tier?.grade] ?? '#6B7280'
  const grade  = emp.tier?.grade ?? '?'
  const active = kpis.filter(k => k.is_active)

  return (
    <motion.div whileHover={{ y: -4, scale: 1.01 }} transition={{ duration: 0.2 }}
      className="glass glass-hover p-5 cursor-pointer select-none border border-white/10 hover:border-white/20">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <p className="text-white font-semibold truncate">{emp.employee_name}</p>
          <p className="text-white/40 text-xs mt-0.5">ID {emp.admin_id}</p>
        </div>
        {/* Score circle */}
        <div className="relative ml-3 shrink-0">
          <svg width="52" height="52" viewBox="0 0 52 52">
            <circle cx="26" cy="26" r="22" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="3" />
            <circle cx="26" cy="26" r="22" fill="none" stroke={tc} strokeWidth="3"
              strokeDasharray={`${2 * Math.PI * 22 * emp.total_score / 100} ${2 * Math.PI * 22}`}
              strokeLinecap="round" strokeDashoffset="0"
              transform="rotate(-90 26 26)"
              style={{ filter: `drop-shadow(0 0 4px ${tc}80)`, transition: 'stroke-dasharray 1s ease' }} />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center flex-col">
            <span className="text-xs font-black" style={{ color: tc }}>{fmtScore(emp.total_score)}</span>
          </div>
        </div>
      </div>

      {/* Tier badge */}
      <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-bold border mb-4"
        style={{ color: tc, borderColor: `${tc}40`, background: `${tc}15` }}>
        Tier {grade} — {TIER_LABEL[grade]}
      </span>

      {/* KPI mini bars */}
      <div className="space-y-2.5">
        {active.slice(0, 3).map((k, i) => {
          const kb  = emp.kpi_breakdown?.[k.key]
          const pct = kb?.success_ratio ?? 0
          const colors = ['#0E7490','#10B981','#F59E0B']
          const c = colors[i % colors.length]
          return (
            <div key={k.key}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-white/40 truncate max-w-[70%]">{k.name.split(' ').slice(0,2).join(' ')}</span>
                <span className="text-white/60 font-medium">{fmtPct(pct)}</span>
              </div>
              <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                <motion.div className="h-full rounded-full"
                  style={{ background: c, boxShadow: `0 0 6px ${c}60` }}
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut', delay: i * 0.15 }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </motion.div>
  )
}
