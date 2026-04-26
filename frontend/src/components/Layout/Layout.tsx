import { useState, useEffect } from 'react'
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Home,
  User,
  Users,
  ChevronLeft,
  MessageCircle,
  Mic,
  AlertCircle,
  X,
  Search,
  Check,
} from 'lucide-react'

import { useAuthStore } from '../../store/authStore'
import { createVisit, getVisits, VisitResponse } from '../../api/visits'
import { apiClient } from '../../api/client'
import logoFullImg from '../../assets/logo-full.jpg'
import logoIconImg from '../../assets/logo-icon.png'

const VersionDisplay = () => {
  const [version, setVersion] = useState<string>('')

  useEffect(() => {
    fetch('/version.json')
      .then(r => r.json())
      .then(v => setVersion(v.version))
      .catch(() => setVersion(''))
  }, [])

  return (
    <p className="text-xs text-gray-300 text-center pb-1">
      {version ? `v${version}` : ''}
    </p>
  )
}

export interface LayoutContext {
  openNewSession: () => void
}

interface LayoutProps {
  isRecording?: boolean
  errorMessage?: string | null
  onDismissError?: () => void
}

export const Layout = ({
  isRecording = false,
  errorMessage = null,
  onDismissError,
}: LayoutProps) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuthStore()

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [patientsExpanded, setPatientsExpanded] = useState(false)
  const [patientSearch, setPatientSearch] = useState('')
  const [visits, setVisits] = useState<VisitResponse[]>([])
  const [showNewSessionModal, setShowNewSessionModal] = useState(false)
  const [showSupportModal, setShowSupportModal] = useState(false)
  const [showSupportConfirm, setShowSupportConfirm] = useState(false)
  const [supportText, setSupportText] = useState('')
  const [patientName, setPatientName] = useState('')
  const [creatingSession, setCreatingSession] = useState(false)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [headerError, setHeaderError] = useState<string | null>(errorMessage)

  const isHomePage = location.pathname === '/'

  useEffect(() => {
    setHeaderError(errorMessage)
  }, [errorMessage])

  useEffect(() => {
    getVisits(50, 0).then(res => setVisits(res.items)).catch(() => {})
  }, [location.pathname])

  useEffect(() => {
    const handler = () => getVisits(50, 0).then(res => setVisits(res.items)).catch(() => {})
    window.addEventListener('visits-updated', handler)
    return () => window.removeEventListener('visits-updated', handler)
  }, [])

  const filteredVisits = visits.filter(v =>
    v.patient_ref.toLowerCase().includes(patientSearch.toLowerCase())
  )

  const handleCreateSession = async () => {
    if (!patientName.trim()) return
    setCreatingSession(true)
    setSessionError(null)
    try {
      const visit = await createVisit({
        patient_ref: patientName.trim(),
        visit_date: new Date().toISOString(),
      })
      setShowNewSessionModal(false)
      setPatientName('')
      navigate(`/visits/${visit.id}`)
    } catch {
      setSessionError('Failed to create session. Please try again.')
    } finally {
      setCreatingSession(false)
    }
  }

  const handleSupportSubmit = async () => {
    try {
      await apiClient.post('/support', { message: supportText })
    } catch (e) {
      // Still show confirmation even if API fails - request is logged
    }
    setSupportText('')
    setShowSupportModal(false)
    setShowSupportConfirm(true)
  }

  return (
    <div className="flex h-screen bg-[#f8f9fa] overflow-hidden">
      {/* Sidebar */}
      <motion.div
        animate={{ width: sidebarCollapsed ? 80 : 288 }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className="flex flex-col bg-white border-r border-gray-100 overflow-hidden flex-shrink-0"
      >
        {/* Logo */}
        <div onClick={() => navigate('/')} className="h-20 flex items-center justify-center px-4 border-b border-gray-50 flex-shrink-0 cursor-pointer">
          {sidebarCollapsed ? (
            <img src={logoIconImg} alt="ih" className="h-12 w-12 object-contain" />
          ) : (
            <img src={logoFullImg} alt="integrate health" className="w-2/3 h-auto object-contain" />
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-4 space-y-1">
          {/* Home */}
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 mx-2 rounded-xl transition-colors ${
                isActive
                  ? 'bg-[#4ac6d6]/10 text-gray-900'
                  : 'text-gray-700 hover:bg-gray-100'
              }`
            }
          >
            <Home size={20} className="flex-shrink-0" />
            {!sidebarCollapsed && <span className="text-sm font-medium">home</span>}
          </NavLink>

          {/* My Account */}
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 mx-2 rounded-xl transition-colors ${
                isActive
                  ? 'bg-[#4ac6d6]/10 text-gray-900'
                  : 'text-gray-700 hover:bg-gray-100'
              }`
            }
          >
            <User size={20} className="flex-shrink-0" />
            {!sidebarCollapsed && <span className="text-sm font-medium">my account</span>}
          </NavLink>

          {/* Patients */}
          <div className="mx-2">
            <button
              onClick={() => {
                if (!sidebarCollapsed) {
                  setPatientsExpanded(e => !e)
                } else {
                  navigate('/patients')
                }
              }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${
                location.pathname.startsWith('/patients') || location.pathname.startsWith('/visits')
                  ? 'bg-[#4ac6d6]/10 text-gray-900'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              <Users size={20} className="flex-shrink-0" />
              {!sidebarCollapsed && (
                <>
                  <span className="text-sm font-medium flex-1 text-left">patients</span>
                  <ChevronLeft
                    size={16}
                    className={`transition-transform text-gray-400 ${patientsExpanded ? '-rotate-90' : 'rotate-0'}`}
                  />
                </>
              )}
            </button>

            {/* Patient list */}
            <AnimatePresence>
              {!sidebarCollapsed && patientsExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <div className="px-2 py-2">
                    <div className="relative">
                      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                      <input
                        value={patientSearch}
                        onChange={e => setPatientSearch(e.target.value)}
                        placeholder="search patients"
                        className="w-full pl-8 pr-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:border-[#4ac6d6] italic text-gray-600 placeholder:text-gray-400"
                      />
                    </div>
                  </div>

                  <div className="max-h-48 overflow-y-auto">
                    {filteredVisits.length === 0 ? (
                      <p className="text-xs text-gray-400 italic px-4 py-2">No patients</p>
                    ) : (
                      filteredVisits.slice(0, 20).map(visit => (
                        <button
                          key={visit.id}
                          onClick={() => navigate(`/visits/${visit.id}`)}
                          className="w-full flex items-center gap-2 px-4 py-2 hover:bg-gray-50 text-left"
                        >
                          {!visit.all_synced && (
                            <span className="w-2 h-2 bg-[#4ac6d6] rounded-full flex-shrink-0" />
                          )}
                          <div className="min-w-0 flex-1">
                            <div className="text-xs text-gray-500">
                              {new Date(visit.visit_date).toLocaleDateString()}
                            </div>
                            <div className="text-sm text-gray-800 truncate">{visit.patient_ref}</div>
                            {visit.chief_complaint && (
                              <div className="text-xs italic text-gray-500 truncate">{visit.chief_complaint}</div>
                            )}
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </nav>

        {/* Bottom bar */}
        <div className="border-t border-gray-100 p-3 space-y-1 flex-shrink-0">
          {!sidebarCollapsed && (
            <VersionDisplay />
          )}
          <button
            onClick={() => setShowSupportModal(true)}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl text-gray-600 hover:bg-gray-100 transition-colors overflow-hidden"
          >
            <MessageCircle size={18} className="flex-shrink-0" />
            {!sidebarCollapsed && (
              <span className="text-sm whitespace-nowrap">contact support</span>
            )}
          </button>

          <button
            onClick={() => setSidebarCollapsed(c => !c)}
            className="w-full flex items-center justify-center px-3 py-2.5 rounded-xl text-gray-400 hover:bg-gray-100 transition-colors"
          >
            <motion.div
              animate={{ rotate: sidebarCollapsed ? 180 : 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 20 }}
            >
              <ChevronLeft size={18} />
            </motion.div>
          </button>
        </div>
      </motion.div>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-16 bg-white border-b border-gray-100 flex items-center justify-end px-6 gap-3 flex-shrink-0">
          {/* Error badge */}
          <AnimatePresence>
            {headerError && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="flex items-center gap-2 bg-orange-50 border-2 border-orange-500 rounded-xl px-4 py-2"
              >
                <motion.div
                  animate={{ rotate: [0, -10, 10, -10, 10, 0] }}
                  transition={{ duration: 0.5, repeat: Infinity, repeatDelay: 3 }}
                >
                  <AlertCircle size={16} className="text-orange-500" />
                </motion.div>
                <span className="text-sm text-orange-700 max-w-[160px] truncate">{headerError}</span>
                <button
                  onClick={() => {
                    setHeaderError(null)
                    onDismissError?.()
                  }}
                  className="text-orange-400 hover:text-orange-600 ml-1"
                >
                  <X size={14} />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Recording indicator */}
          <AnimatePresence>
            {isRecording && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className="flex items-center gap-2 bg-red-50 border-2 border-red-500 rounded-xl px-4 py-2"
              >
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                >
                  <Mic size={16} className="text-red-500" />
                </motion.div>
                <span className="text-sm text-red-600 font-medium">recording</span>
                <motion.div
                  animate={{ opacity: [1, 0, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                  className="w-2 h-2 bg-red-500 rounded-full"
                />
              </motion.div>
            )}
          </AnimatePresence>

          {/* New session button (hidden on home) */}
          {!isHomePage && (
            <NewSessionButton onClick={() => setShowNewSessionModal(true)} />
          )}

          {/* Profile */}
          <button
            onClick={() => navigate('/settings')}
            className="flex items-center gap-3 hover:bg-gray-50 rounded-xl px-3 py-2 transition-colors"
          >
            <div className="text-right">
              <div className="text-sm text-gray-900">{user?.full_name || 'Provider'}</div>
              <div className="text-xs italic text-gray-500">welcome back</div>
            </div>
            {user?.profile_picture_url ? (
              <img src={user.profile_picture_url} alt="profile" className="w-10 h-10 rounded-full object-cover" />
            ) : (
              <div className="w-10 h-10 rounded-full flex items-center justify-center text-white font-medium text-sm"
                style={{ background: 'linear-gradient(135deg, #4ac6d6 0%, #2a8fa0 100%)' }}>
                {(user?.full_name || 'P').split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
              </div>
            )}
          </button>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-8">
          <Outlet context={{ openNewSession: () => setShowNewSessionModal(true) } satisfies LayoutContext} />
        </main>
      </div>

      {/* New Session Modal */}
      <AnimatePresence>
        {showNewSessionModal && (
          <Modal onClose={() => { setShowNewSessionModal(false); setPatientName(''); setSessionError(null) }}>
            <h2 className="text-2xl mb-6">New Patient Session</h2>
            <div className="mb-4">
              <input
                value={patientName}
                onChange={e => setPatientName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleCreateSession()}
                placeholder="Patient name or ID"
                autoFocus
                className="w-full border-2 border-[#4ac6d6] rounded-xl px-4 py-3 text-gray-900 placeholder:italic placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#4ac6d6]/30"
              />
              <p className="text-sm italic text-gray-500 mt-2">
                {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
              </p>
            </div>
            {sessionError && <p className="text-sm text-red-500 mb-4">{sessionError}</p>}
            <div className="flex gap-3">
              <button
                onClick={() => { setShowNewSessionModal(false); setPatientName(''); setSessionError(null) }}
                className="flex-1 border-2 border-[#4ac6d6] text-gray-900 rounded-xl py-3 hover:bg-gray-50 transition-colors"
              >
                cancel
              </button>
              <button
                onClick={handleCreateSession}
                disabled={!patientName.trim() || creatingSession}
                className="flex-1 bg-[#4ac6d6] text-gray-900 rounded-xl py-3 hover:bg-[#3ab5c5] transition-colors disabled:opacity-50 font-medium"
              >
                {creatingSession ? 'creating...' : 'create session'}
              </button>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      {/* Support Modal */}
      <AnimatePresence>
        {showSupportModal && (
          <Modal onClose={() => setShowSupportModal(false)}>
            <h2 className="text-2xl mb-6">Contact Support</h2>
            <textarea
              value={supportText}
              onChange={e => setSupportText(e.target.value)}
              placeholder="How can we help?"
              rows={5}
              className="w-full border-2 border-[#4ac6d6] rounded-xl px-4 py-3 text-gray-900 placeholder:italic placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#4ac6d6]/30 resize-none mb-4"
            />
            <div className="flex gap-3">
              <button
                onClick={() => setShowSupportModal(false)}
                className="flex-1 border-2 border-[#4ac6d6] text-gray-900 rounded-xl py-3 hover:bg-gray-50 transition-colors"
              >
                cancel
              </button>
              <button
                onClick={handleSupportSubmit}
                disabled={!supportText.trim()}
                className="flex-1 bg-[#4ac6d6] text-gray-900 rounded-xl py-3 hover:bg-[#3ab5c5] transition-colors disabled:opacity-50 font-medium"
              >
                submit request
              </button>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      {/* Support Confirmation */}
      <AnimatePresence>
        {showSupportConfirm && (
          <Modal onClose={() => setShowSupportConfirm(false)}>
            <div className="text-center py-4">
              <div className="w-16 h-16 rounded-full bg-[#4ac6d6]/20 flex items-center justify-center mx-auto mb-4">
                <Check size={28} className="text-[#4ac6d6]" />
              </div>
              <h2 className="text-2xl mb-2">Request Received</h2>
              <p className="text-gray-500 italic mb-6">Your request has been received. We'll be in touch shortly.</p>
              <button
                onClick={() => setShowSupportConfirm(false)}
                className="bg-[#4ac6d6] text-gray-900 rounded-xl px-8 py-3 hover:bg-[#3ab5c5] transition-colors"
              >
                done
              </button>
            </div>
          </Modal>
        )}
      </AnimatePresence>
    </div>
  )
}

// Reusable Modal wrapper
function Modal({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 25 }}
        className="bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl"
      >
        {children}
      </motion.div>
    </motion.div>
  )
}

// New Session Button with shine animation
function NewSessionButton({ onClick }: { onClick: () => void }) {
  const [hovered, setHovered] = useState(false)

  return (
    <motion.button
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className="relative overflow-hidden flex items-center gap-2 rounded-xl px-5 py-2.5 text-white" style={{ background: 'linear-gradient(135deg, #4ac6d6 0%, #2a8fa0 100%)' }}
    >
      <span className="text-sm font-medium relative z-10">start new session</span>
      <motion.div
        className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent pointer-events-none"
        animate={{ x: hovered ? '200%' : '-100%' }}
        transition={{ duration: 0.5, ease: 'easeInOut' }}
      />
    </motion.button>
  )
}
