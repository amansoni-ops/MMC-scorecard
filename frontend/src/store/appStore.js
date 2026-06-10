import { create } from 'zustand'

const now = new Date()

export const useStore = create((set, get) => ({
  // ── Auth ────────────────────────────────────────────────────────
  user:      null,
  setUser:   (user) => set({ user }),

  // ── Theme ───────────────────────────────────────────────────────
  theme:     localStorage.getItem('theme') || 'light',
  toggleTheme: () => {
    const next = get().theme === 'light' ? 'dark' : 'light'
    set({ theme: next })
    document.documentElement.setAttribute('data-theme', next)
    document.documentElement.classList.toggle('dark', next === 'dark')
    localStorage.setItem('theme', next)
  },
  initTheme: () => {
    const saved = localStorage.getItem('theme') || 'light'
    set({ theme: saved })
    document.documentElement.setAttribute('data-theme', saved)
    document.documentElement.classList.toggle('dark', saved === 'dark')
  },

  // ── Selected period — persists across all tabs ──────────────────
  // Defaults to current month/year. Never resets on tab change.
  selectedMonth: now.getMonth() + 1,        // 1-12, current month
  selectedYear:  now.getFullYear(),
  setSelectedMonth: (m) => set({ selectedMonth: m }),
  setSelectedYear:  (y) => set({ selectedYear: y }),

  // ── Score data ──────────────────────────────────────────────────
  employees:    [],
  kpis:         [],
  setEmployees: (employees) => set({ employees }),
  setKPIs:      (kpis)      => set({ kpis }),
}))