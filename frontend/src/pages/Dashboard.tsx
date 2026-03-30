import { useState, useEffect } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { motion } from 'framer-motion'

import { getVisits, VisitResponse } from '../api/visits'
import { LayoutContext } from '../components/Layout/Layout'
import sessionGradientImg from '../assets/session-gradient.png'

const formatDate = (dateString: string): string => {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export const Dashboard = () => {
  const navigate = useNavigate()
  const { openNewSession } = useOutletContext<LayoutContext>()
  const [visits, setVisits] = useState<VisitResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [heroHovered, setHeroHovered] = useState(false)

  useEffect(() => {
    setIsLoading(true)
    getVisits(3, 0)
      .then(res => setVisits(res.items))
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }, [])

  return (
    <div className="w-full h-full pt-[5%]">
      <h1 className="text-4xl mb-1">welcome back</h1>
      <p className="italic text-gray-500 mb-8">Here's your practice overview</p>

      {/* Hero CTA */}
      <motion.button
        onHoverStart={() => setHeroHovered(true)}
        onHoverEnd={() => setHeroHovered(false)}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        transition={{ type: 'spring', stiffness: 300, damping: 20 }}
        onClick={openNewSession}
        className="relative w-full h-36 rounded-2xl border-2 border-[#4ac6d6] overflow-hidden mb-10 flex items-center justify-center"
        style={{
          backgroundImage: `url(${sessionGradientImg})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div
          className="absolute inset-0"
          style={{ background: 'linear-gradient(135deg, #4ac6d6cc 0%, #2a8fa0cc 100%)' }}
        />
        <span className="relative z-10 text-3xl text-white drop-shadow-lg font-normal">
          start a new session
        </span>
        {/* Shine sweep */}
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none"
          animate={{ x: heroHovered ? '200%' : '-100%' }}
          transition={{ duration: 0.6, ease: 'easeInOut' }}
        />
      </motion.button>

      {/* Recent Activity */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl">Recent Activity</h2>
        <button
          onClick={() => navigate('/patients')}
          className="text-sm text-[#4ac6d6] hover:text-[#3ab5c5]"
        >
          view all →
        </button>
      </div>

      <div className="bg-white border border-[#4ac6d6] rounded-2xl shadow-md overflow-hidden">
        {isLoading ? (
          <div className="p-8 space-y-4">
            {[0, 1, 2].map(i => (
              <div key={i} className="animate-pulse">
                <div className="h-3 bg-gray-200 rounded w-24 mb-2" />
                <div className="h-4 bg-gray-200 rounded w-48 mb-1" />
                <div className="h-3 bg-gray-200 rounded w-32" />
              </div>
            ))}
          </div>
        ) : visits.length === 0 ? (
          <div className="p-8 text-center">
            <p className="italic text-gray-500">No recent visits</p>
          </div>
        ) : (
          visits.map((visit, idx) => (
            <button
              key={visit.id}
              onClick={() => navigate(`/visits/${visit.id}`)}
              className={`w-full text-left px-8 py-6 hover:bg-gray-50 transition-colors ${
                idx < visits.length - 1 ? 'border-b border-gray-100' : ''
              }`}
            >
              <div className="text-xs text-gray-500 mb-1">{formatDate(visit.visit_date)}</div>
              <div className="text-gray-900 mb-1">
                {visit.patient_ref}
                {visit.chief_complaint && (
                  <span className="text-gray-600"> — {visit.chief_complaint}</span>
                )}
              </div>
              <div className="text-sm italic text-gray-500">{visit.transcription_status}</div>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
