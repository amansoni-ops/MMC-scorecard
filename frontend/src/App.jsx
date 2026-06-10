import { useEffect } from 'react'
import './styles/theme.css'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useStore } from './store/appStore'
import Login          from './pages/Login'
import Dashboard      from './pages/Dashboard'
import EmployeeDetail from './pages/EmployeeDetail'
import Comparison     from './pages/Comparison'
import Reports        from './pages/Reports'
import CacheStatus    from './pages/CacheStatus'
import Preview        from './pages/Preview'
import Layout         from './components/layout/Layout'

function Protected({ children }) {
  const user = useStore(s => s.user)
  return user ? children : <Navigate to="/login" replace />
}

export default function App() {
  const initTheme = useStore(s => s.initTheme)
  useEffect(() => { initTheme() }, [])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Protected><Layout /></Protected>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard"    element={<Dashboard />} />
        <Route path="employee/:id" element={<EmployeeDetail />} />
        <Route path="comparison"   element={<Comparison />} />
        <Route path="reports"      element={<Reports />} />
        <Route path="cache"        element={<CacheStatus />} />
        <Route path="preview"      element={<Preview />} />
      </Route>
    </Routes>
  )
}
