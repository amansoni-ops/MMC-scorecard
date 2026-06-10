import { format } from 'date-fns'

export const fmtScore    = v  => v != null ? v.toFixed(1) : '—'
export const fmtPct      = v  => v != null ? `${v.toFixed(1)}%` : '—'
export const fmtDate     = d  => d ? format(new Date(d), 'dd MMM yyyy') : '—'
export const fmtMonth    = m  => ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m]
export const monthName   = m  => ['January','February','March','April','May','June','July','August','September','October','November','December'][m-1]

export const tierBadge = grade => {
  const map = { A: 'badge-a', B: 'badge-b', C: 'badge-c' }
  return map[grade] ?? 'badge-c'
}

export const CHART_COLORS = ['#0E7490','#10B981','#F59E0B','#EF4444','#8B5CF6','#EC4899','#06B6D4','#84CC16']

export const MONTHS = Array.from({ length: 12 }, (_, i) => ({
  value: i + 1,
  label: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][i],
  full:  ['January','February','March','April','May','June','July','August','September','October','November','December'][i],
}))

export const YEARS = Array.from({ length: 3 }, (_, i) => new Date().getFullYear() - i)
