export function generateInsights(employees, kpis, month) {
  if (!employees?.length) return []
  const insights = []
  const sorted   = [...employees].sort((a, b) => b.total_score - a.total_score)
  const top      = sorted[0]
  const bottom   = sorted[sorted.length - 1]
  const avg      = employees.reduce((s, e) => s + e.total_score, 0) / employees.length
  const tierA    = employees.filter(e => e.tier?.grade === 'A').length
  const tierC    = employees.filter(e => e.tier?.grade === 'C').length

  if (top)
    insights.push({ type: 'success', icon: '🏆', title: 'Top Performer', text: `${top.employee_name} leads with a score of ${top.total_score.toFixed(1)}.` })

  if (tierC > 0)
    insights.push({ type: 'warning', icon: '⚠️', title: 'Attention Required', text: `${tierC} employee${tierC > 1 ? 's' : ''} in Tier C need improvement this month.` })

  if (tierA >= employees.length * 0.5)
    insights.push({ type: 'success', icon: '✨', title: 'Strong Team', text: `${tierA} out of ${employees.length} employees are high performers (Tier A).` })

  // Weakest KPI across the team
  if (kpis?.length) {
    const kpiAvg = {}
    for (const emp of employees) {
      for (const [key, kb] of Object.entries(emp.kpi_breakdown || {})) {
        kpiAvg[key] = kpiAvg[key] || { name: kb.name, total: 0, count: 0 }
        if (kb.success_ratio != null) { kpiAvg[key].total += kb.success_ratio; kpiAvg[key].count++ }
      }
    }
    const weakest = Object.values(kpiAvg).sort((a, b) =>
      (a.total / (a.count || 1)) - (b.total / (b.count || 1))
    )[0]
    if (weakest?.count)
      insights.push({ type: 'info', icon: '📊', title: 'Team Weak Point', text: `${weakest.name} is the weakest KPI at ${(weakest.total / weakest.count).toFixed(1)}% avg success rate.` })
  }

  insights.push({ type: 'info', icon: '📈', title: 'Team Average', text: `Overall team score this month: ${avg.toFixed(1)} / 100.` })

  return insights
}
