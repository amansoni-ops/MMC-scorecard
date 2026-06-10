import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { motion } from 'framer-motion'

const COLORS = { A: '#10B981', B: '#F59E0B', C: '#EF4444' }
const LABELS = { A: 'High Performer', B: 'Consistent', C: 'Needs Improvement' }

export default function TierDonut({ stats }) {
  const data = ['A', 'B', 'C']
    .map(g => ({ name: `Tier ${g}`, label: LABELS[g], value: stats[g], grade: g }))
    .filter(d => d.value > 0)

  return (
    <div className="glass p-6 h-full flex flex-col">
      <h3 className="text-white font-semibold mb-4">Tier Distribution</h3>
      <div className="flex-1 min-h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} cx="50%" cy="50%" innerRadius={60} outerRadius={95}
              paddingAngle={3} dataKey="value" animationBegin={0} animationDuration={800}>
              {data.map(d => (
                <Cell key={d.grade} fill={COLORS[d.grade]}
                  style={{ filter: `drop-shadow(0 0 8px ${COLORS[d.grade]}60)` }} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{ background: '#0F172A', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12 }}
              formatter={(v, n, p) => [v, p.payload.label]}
              labelStyle={{ color: '#fff' }} itemStyle={{ color: '#ffffff80' }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      {/* Legend */}
      <div className="flex justify-around mt-2">
        {['A','B','C'].map(g => (
          <div key={g} className="text-center">
            <p className="text-2xl font-bold" style={{ color: COLORS[g] }}>{stats[g]}</p>
            <p className="text-white/40 text-xs">Tier {g}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
