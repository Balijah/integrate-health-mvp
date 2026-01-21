/**
 * Dashboard page component.
 *
 * Shows list of visits for the authenticated user.
 */

import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Button, Card, Layout } from '../components'
import { useVisitStore } from '../store/visitStore'

/**
 * Format date for display.
 */
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

/**
 * Get status badge color.
 */
const getStatusColor = (status: string): string => {
  switch (status) {
    case 'completed':
      return 'bg-green-100 text-green-800'
    case 'transcribing':
      return 'bg-yellow-100 text-yellow-800'
    case 'failed':
      return 'bg-red-100 text-red-800'
    default:
      return 'bg-gray-100 text-gray-800'
  }
}

export const Dashboard = () => {
  const navigate = useNavigate()
  const { visits, total, isLoading, error, fetchVisits } = useVisitStore()

  useEffect(() => {
    fetchVisits()
  }, [fetchVisits])

  return (
    <Layout>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Visits</h1>
          <p className="mt-1 text-sm text-gray-500">
            {total} total visit{total !== 1 ? 's' : ''}
          </p>
        </div>
        <Link to="/visits/new">
          <Button>New Visit</Button>
        </Link>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Loading state */}
      {isLoading && visits.length === 0 && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-t-transparent mx-auto"></div>
            <p className="mt-2 text-sm text-gray-600">Loading visits...</p>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && visits.length === 0 && (
        <Card>
          <div className="py-12 text-center">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              No visits yet
            </h3>
            <p className="mt-2 text-sm text-gray-500">
              Get started by creating your first patient visit.
            </p>
            <div className="mt-6">
              <Link to="/visits/new">
                <Button>Create First Visit</Button>
              </Link>
            </div>
          </div>
        </Card>
      )}

      {/* Visits list */}
      {visits.length > 0 && (
        <div className="space-y-4">
          {visits.map((visit) => (
            <Card
              key={visit.id}
              hoverable
              onClick={() => navigate(`/visits/${visit.id}`)}
              padding="none"
            >
              <div className="flex items-center justify-between p-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="truncate text-lg font-medium text-gray-900">
                      {visit.patient_ref}
                    </h3>
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusColor(
                        visit.transcription_status
                      )}`}
                    >
                      {visit.transcription_status}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-gray-500">
                    {formatDate(visit.visit_date)}
                  </p>
                  {visit.chief_complaint && (
                    <p className="mt-1 truncate text-sm text-gray-600">
                      {visit.chief_complaint}
                    </p>
                  )}
                </div>
                <div className="ml-4 flex items-center">
                  <svg
                    className="h-5 w-5 text-gray-400"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Pagination placeholder */}
      {total > visits.length && (
        <div className="mt-6 flex justify-center">
          <Button
            variant="secondary"
            onClick={() => fetchVisits(20, visits.length)}
            isLoading={isLoading}
          >
            Load More
          </Button>
        </div>
      )}
    </Layout>
  )
}
