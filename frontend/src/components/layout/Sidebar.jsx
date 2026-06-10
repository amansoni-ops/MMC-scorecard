import { useState, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, BarChart3, GitCompare, Database,
  LogOut, ChevronLeft, Sun, Moon, PlayCircle
} from 'lucide-react'
import { useStore } from '../../store/appStore'
import { logout } from '../../api/scorecard'
import toast from 'react-hot-toast'

const SECTIONS = [
  {
    items: [
      { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard',
        iconBg: '#EEF2FF', iconColor: '#6366F1' },
    ]
  },
  {
    label: 'PERFORMANCE',
    items: [
      { to: '/preview',    icon: PlayCircle,  label: 'Live Preview',
        iconBg: 'linear-gradient(135deg,#C7D2FE,#A5B4FC)', iconColor: '#4338CA',
        isGrad: true },
      { to: '/reports',    icon: BarChart3,   label: 'Score Reports',
        iconBg: '#DCFCE7', iconColor: '#16A34A' },
      { to: '/comparison', icon: GitCompare,  label: 'Comparison',
        iconBg: '#FEF3C7', iconColor: '#D97706' },
    ]
  },
  {
    label: 'SYSTEM',
    items: [
      { to: '/cache', icon: Database, label: 'Cache Status',
        iconBg: '#DBEAFE', iconColor: '#2563EB' },
    ]
  },
]

function NavItem({ to, icon: Icon, label, iconBg, iconColor, isGrad, collapsed }) {
  return (
    <NavLink to={to} title={collapsed ? label : undefined}>
      {({ isActive }) => (
        <motion.div whileHover={{ x: 2 }} transition={{ duration: 0.12 }}
          className="flex items-center gap-3 px-2.5 py-2 rounded-xl cursor-pointer select-none mb-0.5"
          style={{
            background: isActive
              ? 'linear-gradient(135deg,rgba(99,102,241,0.12),rgba(139,92,246,0.08))'
              : 'transparent',
            border: isActive ? '1px solid rgba(99,102,241,0.2)' : '1px solid transparent',
          }}
          onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'var(--bg-hover)' }}
          onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}>

          <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
            style={{
              background: isActive ? 'linear-gradient(135deg,#818CF8,#6366F1)' : iconBg,
              color: isActive ? '#fff' : iconColor,
              boxShadow: isActive ? '0 3px 10px rgba(99,102,241,0.4)' : '0 1px 4px rgba(0,0,0,0.08)',
            }}>
            <Icon size={14} strokeWidth={2} />
          </div>

          {!collapsed && (
            <span className="text-sm font-medium whitespace-nowrap"
              style={{ color: isActive ? '#4338CA' : 'var(--text-muted)' }}>
              {label}
            </span>
          )}
          {isActive && !collapsed && (
            <motion.div layoutId="sidebar-dot" className="ml-auto w-1.5 h-1.5 rounded-full"
              style={{ background: '#6366F1' }} />
          )}
        </motion.div>
      )}
    </NavLink>
  )
}

function ActionBtn({ icon: Icon, grad, iconColor, label, onClick, collapsed, danger }) {
  return (
    <motion.button whileHover={{ x: 2 }} transition={{ duration: 0.12 }}
      onClick={onClick}
      className="flex items-center gap-3 px-2.5 py-2 rounded-xl w-full mb-0.5 cursor-pointer"
      style={{ background: 'transparent', border: '1px solid transparent' }}
      title={collapsed ? label : undefined}
      onMouseEnter={e => { e.currentTarget.style.background = danger ? 'rgba(239,68,68,0.06)' : 'var(--bg-hover)' }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}>
      <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
        style={{ background: grad, color: iconColor, boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
        <Icon size={14} strokeWidth={2} />
      </div>
      {!collapsed && (
        <span className="text-sm font-medium whitespace-nowrap"
          style={{ color: danger ? '#DC2626' : 'var(--text-muted)' }}>
          {label}
        </span>
      )}
    </motion.button>
  )
}


// ── DB Status bar — styled to match ActionBtn theme ───────────────────────
function DBStatusBar({ collapsed }) {
  const [status, setStatus] = useState({ sqlite: null, sqlserver: null })

  useEffect(() => {
    const check = () => {
      fetch('/api/health/db', { credentials: 'include' })
        .then(r => r.ok ? r.json() : Promise.reject())
        .then(d => setStatus({ sqlite: d.sqlite, sqlserver: d.sqlserver }))
        .catch(() => setStatus({ sqlite: false, sqlserver: false }))
    }
    check()
    const t = setInterval(check, 30000)
    return () => clearInterval(t)
  }, [])

  const DbRow = ({ ok, label }) => {
    const color  = ok === null ? '#94A3B8' : ok ? '#10B981' : '#EF4444'
    const grad   = ok === null
      ? 'linear-gradient(135deg,#E2E8F0,#CBD5E1)'
      : ok
        ? 'linear-gradient(135deg,#BBF7D0,#6EE7B7)'
        : 'linear-gradient(135deg,#FECACA,#FCA5A5)'

    if (collapsed) return (
      <div className="flex justify-center py-0.5">
        <span className="w-1.5 h-1.5 rounded-full"
          style={{ background: color, boxShadow: ok ? `0 0 5px ${color}90` : 'none', display:'inline-block' }}/>
      </div>
    )

    return (
      <div className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-xl transition-all"
        style={{ opacity: ok === null ? 0.6 : 1 }}>
        {/* Icon box — same style as ActionBtn */}
        <div className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: grad }}>
          <span className="w-1.5 h-1.5 rounded-full"
            style={{ background: color,
              boxShadow: ok ? `0 0 4px ${color}` : 'none',
              display: 'inline-block' }}/>
        </div>
        <span className="text-xs flex-1" style={{ color: 'var(--text-muted)' }}>{label}</span>
        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md"
          style={{ background: ok ? 'rgba(16,185,129,0.1)' : ok===null ? 'rgba(148,163,184,0.1)' : 'rgba(239,68,68,0.1)',
                   color }}>
          {ok === null ? '…' : ok ? 'OK' : 'Err'}
        </span>
      </div>
    )
  }

  return (
    <div className="mb-1">
      <DbRow ok={status.sqlite}    label="Local DB"/>
      <DbRow ok={status.sqlserver} label="SQL Server"/>
    </div>
  )
}

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const { user, setUser, theme, toggleTheme } = useStore()
  const isDark = theme === 'dark'
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout().catch(() => {})
    setUser(null)
    navigate('/login')
    toast.success('Logged out')
  }

  return (
    <motion.aside
      animate={{ width: collapsed ? 64 : 232 }}
      transition={{ duration: 0.22, ease: [0.4,0,0.2,1] }}
      className="h-screen flex flex-col shrink-0 border-r overflow-hidden"
      style={{ background: 'var(--bg-sidebar)', borderColor: 'var(--border)', zIndex: 20 }}>

      {/* Logo */}
      <div className="flex items-center gap-3 px-3 border-b shrink-0 overflow-hidden"
        style={{ borderColor: 'var(--border)', height: 56 }}>
        <motion.img src="https://www.mmcconvert.com/assets/images/nlogosmall.png"
          alt="MMC" className="shrink-0 object-contain" style={{ width:34, height:34 }}
          animate={{ rotate:[0,3,-3,0] }} transition={{ duration:4, repeat:Infinity, ease:'easeInOut' }}
          onError={e => { e.target.style.display='none' }} />
        {!collapsed && (
          <div className="overflow-hidden">
            <p className="font-bold text-sm leading-tight whitespace-nowrap" style={{ color:'var(--text)' }}>MMC Convert</p>
            <p className="text-xs whitespace-nowrap" style={{ color:'var(--text-faint)' }}>Scorecard</p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {SECTIONS.map((sec, si) => (
          <div key={si} className="mb-1">
            {!collapsed && sec.label && (
              <p className="px-2.5 pt-3 pb-1.5 text-[10px] font-bold tracking-[0.1em] uppercase"
                style={{ color:'var(--text-faint)' }}>{sec.label}</p>
            )}
            {sec.items.map(item => (
              <NavItem key={item.to} {...item} collapsed={collapsed} />
            ))}
          </div>
        ))}
      </nav>

      {/* Bottom */}
      <div className="px-2 py-3 border-t" style={{ borderColor:'var(--border)' }}>
        {!collapsed && (
          <div className="flex items-center gap-2.5 px-2.5 py-2 mb-1 rounded-xl"
            style={{ background:'var(--bg-hover)' }}>
            <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
              style={{ background:'linear-gradient(135deg,#6366F1,#8B5CF6)' }}>
              {user?.username?.[0]?.toUpperCase()}
            </div>
            <div className="min-w-0 overflow-hidden">
              <p className="text-xs font-semibold capitalize truncate" style={{ color:'var(--text)' }}>{user?.username}</p>
              <p className="text-xs capitalize" style={{ color:'var(--text-faint)' }}>{user?.role}</p>
            </div>
          </div>
        )}

        <ActionBtn
          icon={isDark ? Sun : Moon}
          grad={isDark ? 'linear-gradient(135deg,#FDE68A,#FCD34D)' : 'linear-gradient(135deg,#C7D2FE,#A5B4FC)'}
          iconColor={isDark ? '#B45309' : '#4338CA'}
          label={isDark ? 'Light Mode' : 'Dark Mode'}
          collapsed={collapsed} onClick={toggleTheme} />
        <ActionBtn
          icon={LogOut}
          grad="linear-gradient(135deg,#FECACA,#FCA5A5)"
          iconColor="#DC2626" label="Logout"
          collapsed={collapsed} onClick={handleLogout} danger />

        <DBStatusBar collapsed={collapsed}/>

        <button onClick={() => setCollapsed(c => !c)}
          className="w-full flex items-center justify-center gap-2 py-2 mt-1 rounded-xl text-xs font-medium transition-all"
          style={{ border:'1px solid var(--border)', color:'var(--text-muted)', background:'var(--bg-hover)' }}>
          <motion.span animate={{ rotate: collapsed ? 180 : 0 }} transition={{ duration:0.25 }}>
            <ChevronLeft size={13} />
          </motion.span>
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </motion.aside>
  )
}
