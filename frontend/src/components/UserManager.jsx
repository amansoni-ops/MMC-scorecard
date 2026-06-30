import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { X, UserPlus, Trash2, KeyRound, Shield, Eye } from 'lucide-react'
import toast from 'react-hot-toast'

export default function UserManager({ onClose }) {
  const [users,   setUsers]   = useState([])
  const [loading, setLoading] = useState(true)
  const isDark = document.documentElement.classList.contains('dark') ||
                 document.documentElement.getAttribute('data-theme') === 'dark'

  // New-user form state
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole,     setNewRole]     = useState('viewer')
  const [creating,    setCreating]    = useState(false)

  // Per-user password-reset state (which user's reset field is open, and its value)
  const [resetTargetId, setResetTargetId] = useState(null)
  const [resetValue,     setResetValue]    = useState('')
  const [resetting,      setResetting]     = useState(false)

  const loadUsers = () => {
    setLoading(true)
    fetch('/api/users', { credentials: 'include' })
      .then(r => r.json())
      .then(d => setUsers(d.users ?? []))
      .catch(() => toast.error('Could not load users'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadUsers() }, [])

  const createUser = async () => {
    if (!newUsername.trim()) { toast.error('Username is required'); return }
    if (newPassword.length < 6) { toast.error('Password must be at least 6 characters'); return }
    setCreating(true)
    try {
      const res = await fetch('/api/users', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: newUsername.trim(), password: newPassword, role: newRole }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
      toast.success(`User "${newUsername.trim()}" created`)
      setNewUsername(''); setNewPassword(''); setNewRole('viewer')
      loadUsers()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setCreating(false)
    }
  }

  const deleteUser = async (user) => {
    if (!window.confirm(`Delete user "${user.username}"? This cannot be undone.`)) return
    try {
      const res = await fetch(`/api/users/${user.id}`, { method: 'DELETE', credentials: 'include' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
      toast.success(`User "${user.username}" deleted`)
      loadUsers()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const submitReset = async (user) => {
    if (resetValue.length < 6) { toast.error('Password must be at least 6 characters'); return }
    setResetting(true)
    try {
      const res = await fetch(`/api/users/${user.id}/password`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_password: resetValue }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
      toast.success(`Password reset for "${user.username}"`)
      setResetTargetId(null); setResetValue('')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setResetting(false)
    }
  }

  return (
    <motion.div className="fixed inset-0 z-50 flex items-center justify-center"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>

      {/* Overlay — semi-transparent so dashboard is visible behind */}
      <div className="absolute inset-0"
        style={{ background: 'rgba(0,0,0,0.28)', backdropFilter: 'blur(2px)' }}
        onClick={onClose}/>

      {/* Modal — frosted glass, same pattern as KPIWeightManager */}
      <motion.div className="relative flex flex-col"
        initial={{ scale: 0.93, y: 12 }} animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.93, y: 12 }}
        style={{
          width: 560,
          maxHeight: '88vh',
          background: isDark
            ? 'rgba(30, 30, 30, 0.96)'
            : 'rgba(255, 255, 255, 0.96)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: isDark
            ? '1px solid rgba(80,80,80,0.5)'
            : '1px solid rgba(255,255,255,0.8)',
          borderRadius: 20,
          boxShadow: '0 20px 60px rgba(0,0,0,0.22), 0 2px 12px rgba(0,0,0,0.12)',
          overflow: 'hidden',
        }}>

        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-6 pb-4 shrink-0">
          <div>
            <p className="font-bold text-base" style={{ color: 'var(--text)' }}>User Management</p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              Create accounts, reset passwords, manage access
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg transition-colors"
            style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)' }}>
            <X size={15}/>
          </button>
        </div>

        {/* New user form */}
        <div className="px-6 pb-4 shrink-0">
          <div className="rounded-xl p-4 border"
            style={{
              background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(99,102,241,0.04)',
              borderColor: 'var(--border)',
            }}>
            <p className="text-xs font-bold uppercase tracking-wider mb-3"
              style={{ color: 'var(--text-faint)' }}>Add New User</p>
            <div className="flex gap-2 mb-2">
              <input
                type="text" placeholder="Username" value={newUsername}
                onChange={e => setNewUsername(e.target.value)}
                className="form-input flex-1" style={{ fontSize: 13 }}/>
              <select value={newRole} onChange={e => setNewRole(e.target.value)}
                className="form-input" style={{ fontSize: 13, width: 110 }}>
                <option value="viewer">Viewer</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="flex gap-2">
              <input
                type="password" placeholder="Password (min 6 characters)" value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                className="form-input flex-1" style={{ fontSize: 13 }}/>
              <button onClick={createUser} disabled={creating}
                className="btn btn-primary shrink-0" style={{ paddingLeft: 14, paddingRight: 14 }}>
                <UserPlus size={13}/>
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        </div>

        {/* User list — scrollable */}
        <div className="flex-1 overflow-y-auto px-6 space-y-2 pb-4">
          {loading && (
            <p className="text-sm text-center py-6" style={{ color: 'var(--text-muted)' }}>
              Loading users…
            </p>
          )}
          {!loading && users.length === 0 && (
            <p className="text-sm text-center py-6" style={{ color: 'var(--text-muted)' }}>
              No users found.
            </p>
          )}
          {!loading && users.map(u => {
            const isResetOpen = resetTargetId === u.id
            const isAdminRole = u.role === 'admin'
            return (
              <div key={u.id} className="rounded-xl p-3 border"
                style={{
                  background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.9)',
                  borderColor: 'var(--border)',
                }}>
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                    style={{
                      background: isAdminRole ? '#6366F118' : 'var(--bg-hover)',
                      color: isAdminRole ? '#6366F1' : 'var(--text-muted)',
                    }}>
                    {isAdminRole ? <Shield size={14}/> : <Eye size={14}/>}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm" style={{ color: 'var(--text)' }}>{u.username}</p>
                    <p className="text-xs capitalize" style={{ color: 'var(--text-faint)' }}>{u.role}</p>
                  </div>
                  <button
                    onClick={() => { setResetTargetId(isResetOpen ? null : u.id); setResetValue('') }}
                    title="Reset password"
                    className="p-1.5 rounded-lg transition-colors shrink-0"
                    style={{
                      background: isResetOpen ? '#F59E0B18' : 'var(--bg-hover)',
                      color: isResetOpen ? '#F59E0B' : 'var(--text-faint)',
                    }}>
                    <KeyRound size={14}/>
                  </button>
                  <button
                    onClick={() => deleteUser(u)}
                    title="Delete user"
                    className="p-1.5 rounded-lg transition-colors shrink-0"
                    style={{ background: 'var(--bg-hover)', color: '#EF4444' }}>
                    <Trash2 size={14}/>
                  </button>
                </div>

                {isResetOpen && (
                  <div className="flex gap-2 mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
                    <input
                      type="password" placeholder="New password (min 6 characters)"
                      value={resetValue} onChange={e => setResetValue(e.target.value)}
                      className="form-input flex-1" style={{ fontSize: 13 }}/>
                    <button onClick={() => submitReset(u)} disabled={resetting}
                      className="btn btn-primary shrink-0" style={{ fontSize: 12, paddingLeft: 12, paddingRight: 12 }}>
                      {resetting ? 'Saving…' : 'Save'}
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex shrink-0"
          style={{
            borderColor: 'var(--border)',
            background: isDark ? 'rgba(30,30,30,0.8)' : 'rgba(255,255,255,0.8)',
          }}>
          <button onClick={onClose} className="btn btn-secondary flex-1">Close</button>
        </div>
      </motion.div>
    </motion.div>
  )
}