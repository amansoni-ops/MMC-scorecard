import { motion } from 'framer-motion'

const COLORS = {
  indigo: { icon: '#6366F1', bg: '#EEF2FF', text: '#6366F1', border: '#C7D2FE' },
  green:  { icon: '#16A34A', bg: '#DCFCE7', text: '#16A34A', border: '#86EFAC' },
  red:    { icon: '#DC2626', bg: '#FEE2E2', text: '#DC2626', border: '#FCA5A5' },
  amber:  { icon: '#D97706', bg: '#FEF3C7', text: '#D97706', border: '#FCD34D' },
}

export default function StatCard({ label, value, sub, color = 'indigo', icon: Icon }) {
  const c = COLORS[color] ?? COLORS.indigo
  return (
    <motion.div
      whileHover={{ y: -3 }}
      transition={{ duration: 0.15 }}
      className="card p-5 relative overflow-hidden"
      style={{ border: `1px solid ${c.border}` }}
    >
      {/* Soft background blob */}
      <div className="absolute -bottom-6 -right-6 w-28 h-28 rounded-full pointer-events-none"
        style={{ background: c.bg, opacity: 0.6 }} />

      <div className="relative z-10">
        <div className="flex items-start justify-between mb-4">
          <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-faint)' }}>
            {label}
          </p>
          <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
            style={{ background: c.bg, color: c.icon }}>
            <Icon size={18} />
          </div>
        </div>

        {/* Plain colored number — works in all browsers */}
        <p className="text-4xl font-light tracking-tight" style={{ color: c.text }}>
          {value}
        </p>
        {sub && (
          <p className="text-xs mt-1.5" style={{ color: 'var(--text-faint)' }}>{sub}</p>
        )}
      </div>
    </motion.div>
  )
}
