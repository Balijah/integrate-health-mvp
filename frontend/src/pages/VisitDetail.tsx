/**
 * Visit Detail page component.
 *
 * Shows details of a single visit with options to record audio and view transcript.
 */

import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

import { AudioRecorder, Button, Card, Layout } from '../components'
import { uploadAudio } from '../api/visits'
import { useVisitStore } from '../store/visitStore'

/**
 * Format date for display.
 */
const formatDate = (dateString: string): string => {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/**
 * Format duration in seconds to MM:SS or HH:MM:SS.
 */
const formatDuration = (seconds: number): string => {
  const hrs = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60

  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`
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

export const VisitDetail = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const {
    currentVisit,
    isLoading,
    error,
    fetchVisit,
    deleteVisit,
    clearCurrentVisit,
  } = useVisitStore()

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadError, setUploadError] = useState<string | null>(null)

  useEffect(() => {
    if (id) {
      fetchVisit(id)
    }
    return () => clearCurrentVisit()
  }, [id, fetchVisit, clearCurrentVisit])

  const handleDelete = async () => {
    if (!id) return
    setIsDeleting(true)
    const success = await deleteVisit(id)
    if (success) {
      navigate('/dashboard')
    }
    setIsDeleting(false)
    setShowDeleteConfirm(false)
  }

  const handleRecordingComplete = async (blob: Blob) => {
    if (!id) return

    setIsUploading(true)
    setUploadProgress(0)
    setUploadError(null)

    try {
      await uploadAudio(id, blob, (progress) => {
        setUploadProgress(progress)
      })
      // Refresh visit data to show updated audio info
      await fetchVisit(id)
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to upload audio'
      setUploadError(errorMessage)
    } finally {
      setIsUploading(false)
    }
  }

  if (isLoading && !currentVisit) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-t-transparent mx-auto"></div>
            <p className="mt-2 text-sm text-gray-600">Loading visit...</p>
          </div>
        </div>
      </Layout>
    )
  }

  if (error) {
    return (
      <Layout>
        <div className="rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-2"
            onClick={() => navigate('/dashboard')}
          >
            Back to Dashboard
          </Button>
        </div>
      </Layout>
    )
  }

  if (!currentVisit) {
    return (
      <Layout>
        <Card>
          <div className="py-12 text-center">
            <p className="text-gray-500">Visit not found</p>
            <Button
              variant="secondary"
              className="mt-4"
              onClick={() => navigate('/dashboard')}
            >
              Back to Dashboard
            </Button>
          </div>
        </Card>
      </Layout>
    )
  }

  return (
    <Layout>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <button
            onClick={() => navigate('/dashboard')}
            className="mb-2 flex items-center text-sm text-gray-500 hover:text-gray-700"
          >
            <svg
              className="mr-1 h-4 w-4"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z"
                clipRule="evenodd"
              />
            </svg>
            Back to Visits
          </button>
          <h1 className="text-2xl font-bold text-gray-900">
            {currentVisit.patient_ref}
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            {formatDate(currentVisit.visit_date)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${getStatusColor(
              currentVisit.transcription_status
            )}`}
          >
            {currentVisit.transcription_status}
          </span>
        </div>
      </div>

      <div className="space-y-6">
        {/* Chief Complaint */}
        <Card title="Chief Complaint">
          <p className="text-gray-700">
            {currentVisit.chief_complaint || 'No chief complaint recorded'}
          </p>
        </Card>

        {/* Audio Recording */}
        <Card
          title="Audio Recording"
          subtitle={
            currentVisit.audio_file_path
              ? `Duration: ${formatDuration(currentVisit.audio_duration_seconds || 0)}`
              : 'Record audio for this visit'
          }
        >
          {uploadError && (
            <div className="mb-4 rounded-md bg-red-50 p-3">
              <p className="text-sm text-red-700">{uploadError}</p>
            </div>
          )}

          {isUploading && (
            <div className="mb-4">
              <div className="flex items-center justify-between text-sm text-gray-600">
                <span>Uploading...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-gray-200">
                <div
                  className="h-full bg-primary-500 transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {currentVisit.audio_file_path ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg bg-green-50 p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100">
                    <svg
                      className="h-5 w-5 text-green-600"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                  <div>
                    <p className="font-medium text-green-800">
                      Audio uploaded successfully
                    </p>
                    <p className="text-sm text-green-600">
                      Duration: {formatDuration(currentVisit.audio_duration_seconds || 0)}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <AudioRecorder
              onRecordingComplete={handleRecordingComplete}
              isUploading={isUploading}
              maxDurationSeconds={3600}
            />
          )}
        </Card>

        {/* Transcript */}
        <Card
          title="Transcript"
          subtitle={
            currentVisit.transcription_status === 'completed'
              ? 'Transcription complete'
              : currentVisit.transcription_status === 'transcribing'
              ? 'Transcription in progress...'
              : 'Awaiting audio upload'
          }
        >
          {currentVisit.transcript ? (
            <div className="prose max-w-none">
              <p className="whitespace-pre-wrap text-gray-700">
                {currentVisit.transcript}
              </p>
            </div>
          ) : (
            <div className="rounded-md bg-gray-50 p-4 text-center">
              <p className="text-sm text-gray-500">
                Transcript will appear here after audio is uploaded and
                transcribed
              </p>
            </div>
          )}
        </Card>

        {/* SOAP Note Placeholder */}
        <Card
          title="SOAP Note"
          subtitle="Generated note will appear here"
        >
          <div className="rounded-md bg-gray-50 p-4 text-center">
            <p className="text-sm text-gray-500">
              SOAP note generation will be available in Phase 6
            </p>
          </div>
        </Card>

        {/* Actions */}
        <Card padding="sm">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Created: {formatDate(currentVisit.created_at)}
            </p>
            <Button
              variant="danger"
              size="sm"
              onClick={() => setShowDeleteConfirm(true)}
            >
              Delete Visit
            </Button>
          </div>
        </Card>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900">
              Delete Visit
            </h3>
            <p className="mt-2 text-sm text-gray-500">
              Are you sure you want to delete this visit? This action cannot be
              undone and will also delete any associated audio and notes.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <Button
                variant="secondary"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={handleDelete}
                isLoading={isDeleting}
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
