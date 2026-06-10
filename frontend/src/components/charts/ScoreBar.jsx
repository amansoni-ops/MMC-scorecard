import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts'
import { fmtScore } from '../../utils/formatters'

const TIER_COLOR = { A: '#10B981', B: '#F59E0B', C: '#EF4444' }

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="custom-tooltip">
      <p className="text-white font-semibold text-sm">{d.employee_name}</p>
      <p style={{ color: TIER_COLOR[d.tier?.grade] }} className="text-lg font-bold">{fmtScore(d.total_score)}</p>
      <p className="text-white/40 text-xs">Tier {d.tier?.grade} — {d.tier?.label}</p>
    </div>
  )
}

export default function ScoreBar({ employees }) {
  const data = [...employees].sort((a, b) => b.total_score - a.total_score)
  const names = data.map(e => e.employee_name.split(' ')[0])

  return (
    <div className="glass p-6 h-full flex flex-col">
      <h3 className="text-white font-semibold mb-4">Employee Scores</h3>
      <div className="flex-1 min-h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 5, right: 10, bottom: 40, left: 0 }}>
            <XAxis dataKey="employee_name"
              tick={{ fill: '#ffffff40', fontSize: 11 }}
              tickFormatter={n => n.split(' ')[0]}
              angle={-35} textAnchor="end" interval={0} />
            <YAxis domain={[0, 100]} tick={{ fill: '#ffffff40', fontSize: 11 }} />
            <ReferenceLine y={90} stroke="#10B98140" strokeDasharray="4 4" label={{ value: 'A', fill: '#10B981', fontSize: 11 }} />
            <ReferenceLine y={60} stroke="#F59E0B40" strokeDasharray="4 4" label={{ value: 'B', fill: '#F59E0B', fontSize: 11 }} />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
            <Bar dataKey="total_score" radius={[6,6,0,0]} maxBarSize={36} animationDuration={800}>
              {data.map((e, i) => (
                <Cell key={i} fill={TIER_COLOR[e.tier?.grade] ?? '#0E7490'}
                  style={{ filter: `drop-shadow(0 0 6px ${TIER_COLOR[e.tier?.grade]}60)` }} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
