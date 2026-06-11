import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  withCredentials: true,
  timeout: 300000,   // 5 minutes — SQL Server queries can be slow on first run
})

api.interceptors.request.use(req => {
  console.log(`[API →] ${req.method?.toUpperCase()} ${req.url} - scorecard.js:10`, req.params || '')
  return req
})

api.interceptors.response.use(
  res => {
    console.log(`[API ✓] ${res.status} ${res.config.url} - scorecard.js:16`)
    return res
  },
  err => {
    const status = err.response?.status
    const url    = err.config?.url
    console.error(`[API ✗] ${status ?? 'NETWORK'} ${url} - scorecard.js:22`, err.message)
    return Promise.reject(err)
  }
)

export const login    = (u, p) => api.post('/login',  { username: u, password: p })
export const logout   = ()     => api.post('/logout')
export const getMe    = ()     => api.get('/me')

export const getScores        = (month, year) => api.get('/scores',             { params: { month, year } })
export const getEmployeeScore = (id, m, y)    => api.get(`/scores/${id}`,       { params: { month: m, year: y } })
export const getEmployeeTrend = (id, year)    => api.get(`/scores/${id}/trend`, { params: { year } })

export const getKPIs      = ()        => api.get('/kpis')
export const updateWeight = (key, w)  => api.put(`/kpis/${key}/weight`, { weight: w })
export const toggleKPI    = (key, on) => api.put(`/kpis/${key}/toggle`, { is_active: on })

export const getNote  = (id, m, y)       => api.get(`/notes/${id}`,  { params: { month: m, year: y } })
export const saveNote = (id, m, y, text) => api.post(`/notes/${id}`, { note_text: text }, { params: { month: m, year: y } })

export const getCacheStatus = ()     => api.get('/cache/status')
export const refreshCache   = (m, y) => api.post('/cache/refresh', null, { params: { month: m, year: y } })
