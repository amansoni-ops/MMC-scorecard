import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid, Legend } from 'recharts'
import { fmtScore, fmtMonth } from '../../utils/formatters'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="custom-tooltip">
      <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>{fmtMonth(label)}</p>
      {payload.map((p,i) => (
        <div key={i} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-base font-light" style={{ color: p.color }}>{fmtScore(p.value)}</span>
          {p.name && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{p.name}</span>}
        </div>
      ))}
    </div>
  )
}

export default function TrendLine({ trend=[], trend2=[], color1='#0E7490', color2='#8B5CF6', name1, name2 }) {
  const data = trend.map(t => {
    const t2 = trend2.find(x => x.month === t.month)
    return { month: t.month, score1: t.total_score, score2: t2?.total_score ?? null }
  })

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top:5, right:20, bottom:5, left:0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="month" tickFormatter={fmtMonth} tick={{ fill: 'var(--text-muted)', fontSize:12 }} />
        <YAxis domain={[0,100]} tick={{ fill: 'var(--text-muted)', fontSize:12 }} />
        <ReferenceLine y={90} stroke="#10B98130" strokeDasharray="4 4" />
        <ReferenceLine y={60} stroke="#F59E0B30" strokeDasharray="4 4" />
        <Tooltip content={<CustomTooltip />} />
        {(name1||name2) && <Legend wrapperStyle={{ color: 'var(--text-muted)', fontSize:12 }} />}
        <Line type="monotone" dataKey="score1" name={name1??'Score'} stroke={color1} strokeWidth={2.5}
          dot={{ fill:color1, r:4, strokeWidth:0 }} activeDot={{ r:6, strokeWidth:0 }}
          connectNulls animationDuration={800} />
        {trend2.length > 0 && (
          <Line type="monotone" dataKey="score2" name={name2??'Score 2'} stroke={color2} strokeWidth={2.5}
            strokeDasharray="6 3" dot={{ fill:color2, r:4, strokeWidth:0 }} activeDot={{ r:6, strokeWidth:0 }}
            connectNulls animationDuration={800} />
        )}
      </LineChart>
    </ResponsiveContainer>
  )
}
