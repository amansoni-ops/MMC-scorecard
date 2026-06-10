import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Eye, EyeOff } from 'lucide-react'
import { login } from '../api/scorecard'
import { useStore } from '../store/appStore'
import toast from 'react-hot-toast'

// ── Floating particle (light theme — soft indigo/purple tones) ────────────
function Particle({ x, y, size, delay, duration }) {
  return (
    <motion.div
      className="absolute rounded-full pointer-events-none"
      style={{
        left: `${x}%`, top: `${y}%`,
        width: size, height: size,
        background: `radial-gradient(circle, rgba(99,102,241,0.18) 0%, rgba(139,92,246,0.06) 100%)`,
      }}
      animate={{
        y: [0, -60, 0],
        x: [0, Math.sin(delay) * 20, 0],
        opacity: [0.15, 0.5, 0.15],
        scale: [1, 1.3, 1],
      }}
      transition={{ duration, repeat: Infinity, delay, ease: 'easeInOut' }}
    />
  )
}

const PARTICLES = Array.from({ length: 18 }, (_, i) => ({
  x: Math.random() * 100,
  y: Math.random() * 100,
  size: `${24 + Math.random() * 56}px`,
  delay: i * 0.4,
  duration: 5 + Math.random() * 5,
}))

export default function Login() {
  const [form, setForm]       = useState({ username: '', password: '' })
  const [show, setShow]       = useState(false)
  const [loading, setLoading] = useState(false)
  const [logoLoaded, setLogoLoaded] = useState(false)
  const setUser  = useStore(s => s.setUser)
  const navigate = useNavigate()

  const handleSubmit = async e => {
    e.preventDefault()
    if (!form.username || !form.password) return toast.error('Please fill all fields')
    setLoading(true)
    try {
      const { data } = await login(form.username, form.password)
      setUser(data.user)
      toast.success(`Welcome back, ${data.user.username}!`)
      navigate('/dashboard')
    } catch (err) {
      const msg = err.response?.data?.error || 'Invalid credentials'
      toast.error(msg)
    } finally { setLoading(false) }
  }

  return (
    <div className="min-h-screen relative overflow-hidden flex items-center justify-center"
      style={{ background: 'linear-gradient(135deg, #F0F4FF 0%, #FAFAFA 50%, #F0FFF4 100%)' }}>

      {/* ── Particles ─────────────────────────────────────────────────── */}
      {PARTICLES.map((p, i) => <Particle key={i} {...p} />)}

      {/* ── Soft blobs ────────────────────────────────────────────────── */}
      <div className="absolute top-[-120px] left-[-80px] w-80 h-80 rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)' }} />
      <div className="absolute bottom-[-100px] right-[-60px] w-72 h-72 rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(16,185,129,0.10) 0%, transparent 70%)' }} />
      <div className="absolute top-[40%] right-[10%] w-48 h-48 rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(245,158,11,0.08) 0%, transparent 70%)' }} />

      {/* ── Grid overlay ──────────────────────────────────────────────── */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.025]"
        style={{
          backgroundImage: 'linear-gradient(#6366F1 1px, transparent 1px), linear-gradient(90deg, #6366F1 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }} />

      {/* ── Card ──────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 32, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.45, ease: [0.23, 1, 0.32, 1] }}
        className="relative z-10 w-full max-w-sm mx-4 rounded-2xl overflow-hidden"
        style={{
          background: 'rgba(255,255,255,0.92)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(99,102,241,0.15)',
          boxShadow: '0 20px 60px rgba(99,102,241,0.15), 0 4px 16px rgba(0,0,0,0.06)',
        }}>

        {/* Top accent bar */}
        <div className="h-1 w-full" style={{ background: 'linear-gradient(90deg, #6366F1, #8B5CF6, #10B981)' }} />

        <div className="p-8">
          {/* Logo + brand */}
          <div className="text-center mb-8">
            <motion.div
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.5, type: 'spring', bounce: 0.4 }}
              className="inline-block mb-4"
            >
              <motion.img
                src="https://www.mmcconvert.com/assets/images/nlogosmall.png"
                alt="MMC Convert"
                style={{ width: 80, height: 80, objectFit: 'contain' }}
                animate={{ y: [0, -6, 0] }}
                transition={{ duration: 3.5, repeat: Infinity, ease: 'easeInOut' }}
                onLoad={() => setLogoLoaded(true)}
                onError={e => {
                  e.target.style.display = 'none'
                  // Fallback: show text logo
                }}
              />
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: logoLoaded ? 1 : 1, y: 0 }}
              transition={{ delay: 0.25 }}>
              <h1 className="text-xl font-bold" style={{ color: '#0F172A' }}>MMC Convert</h1>
              <p className="text-sm mt-0.5" style={{ color: '#64748B' }}>Employee Performance Scorecard</p>
            </motion.div>
          </div>

          {/* Form */}
          <motion.form onSubmit={handleSubmit}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
            className="space-y-4">

            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: '#475569' }}>
                Username
              </label>
              <input
                type="text"
                value={form.username}
                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                placeholder="Enter username"
                className="form-input w-full"
                style={{ background: '#F8FAFC', borderColor: '#E2E8F0', color: '#0F172A' }}
                autoComplete="username"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: '#475569' }}>
                Password
              </label>
              <div className="relative">
                <input
                  type={show ? 'text' : 'password'}
                  value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  placeholder="Enter password"
                  className="form-input w-full pr-10"
                  style={{ background: '#F8FAFC', borderColor: '#E2E8F0', color: '#0F172A' }}
                  autoComplete="current-password"
                />
                <button type="button" onClick={() => setShow(s => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors"
                  style={{ color: '#94A3B8' }}>
                  {show ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <motion.button
              type="submit"
              disabled={loading}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              className="btn btn-primary w-full justify-center py-2.5 mt-2 text-sm font-semibold"
              style={{ borderRadius: 12 }}>
              <AnimatePresence mode="wait">
                {loading ? (
                  <motion.div key="l" initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}
                    className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                    Signing in…
                  </motion.div>
                ) : (
                  <motion.span key="t" initial={{ opacity:0 }} animate={{ opacity:1 }}>
                    Sign In
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.button>
          </motion.form>

          {/* Hint */}
          <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ delay:0.5 }}
            className="mt-5 p-3 rounded-xl text-xs"
            style={{ background: '#F1F5F9', color: '#64748B' }}>
            <p className="font-semibold mb-0.5" style={{ color: '#334155' }}>Default credentials</p>
            <p>admin / admin123 &nbsp;·&nbsp; manager / Manager@123</p>
          </motion.div>
        </div>
      </motion.div>
    </div>
  )
}
