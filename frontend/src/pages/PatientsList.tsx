import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'

import { getVisits, VisitResponse } from '../api/visits'

const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export const PatientsList = () => {
  const [visits, setVisits] = useState<VisitResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    setIsLoading(true)
    getVisits(100, 0)
      .then(res => setVisits(res.items))
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }, [])

  const filteredVisits = useMemo(() => {
    const q = searchQuery.toLowerCase()
    if (!q) return visits
    return visits.filter(v =>
      v.patient_ref.toLowerCase().includes(q) ||
      (v.chief_complaint || '').toLowerCase().includes(q)
    )
  }, [visits, searchQuery])

  return (
    <div className="w-full h-full">
      <div className="mb-8 mt-12">
        <h1 className="text-4xl mb-1">Patients</h1>
        <p className="italic text-gray-500">View all patient records</p>
      </div>

      {/* Search */}
      <div className="mb-8 max-w-md">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="find a patient"
            className="w-full pl-10 pr-4 py-3 border border-[#4ac6d6] rounded-xl text-gray-900 placeholder:italic placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#4ac6d6]/30 bg-white"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[0, 1, 2, 3, 4, 5].map(i => (
            <div key={i} className="bg-white border border-[#4ac6d6] rounded-2xl p-6 animate-pulse">
              <div className="h-3 bg-gray-200 rounded w-20 mb-3" />
              <div className="h-5 bg-gray-200 rounded w-32 mb-2" />
              <div className="h-3 bg-gray-200 rounded w-48" />
            </div>
          ))}
        </div>
      ) : filteredVisits.length === 0 ? (
        <div className="text-center py-12 text-gray-500 italic">
          {searchQuery ? `No patients found for "${searchQuery}"` : 'No patients yet'}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredVisits.map(visit => (
            <Link
              to={`/visits/${visit.id}`}
              key={visit.id}
              className="bg-white border border-[#4ac6d6] rounded-2xl p-6 hover:shadow-lg hover:border-[#4ac6d6] transition-all block"
            >
              <div className="text-xs text-gray-500 mb-2">{formatDate(visit.visit_date)}</div>
              <div className="text-lg text-gray-900 mb-2 font-medium">{visit.patient_ref}</div>
              {visit.chief_complaint && (
                <div className="text-sm italic text-gray-500 line-clamp-2">{visit.chief_complaint}</div>
              )}
              <div className="mt-3">
                <span className={`text-xs px-2 py-1 rounded-full ${
                  visit.transcription_status === 'completed'
                    ? 'bg-green-100 text-green-700'
                    : visit.transcription_status === 'failed'
                    ? 'bg-red-100 text-red-700'
                    : 'bg-gray-100 text-gray-600'
                }`}>
                  {visit.transcription_status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
