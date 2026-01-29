/**
 * Visit Detail page component.
 *
 * Shows details of a single visit with options to record audio and view transcript.
 */

import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

import { AudioRecorder, Button, Card, Layout, NoteEditor } from '../components'
import { LiveRecorder } from '../components/LiveRecorder'
import { useToast } from '../components/Toast'
import { uploadAudio, retryTranscription } from '../api/visits'
import { generateNote, getNote, NoteResponse } from '../api/notes'
import { useTranscriptionPolling } from '../hooks'
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
  const toast = useToast()
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
  const [isRetrying, setIsRetrying] = useState(false)

  // Recording mode: 'upload' for traditional recording, 'live' for live transcription
  const [recordingMode, setRecordingMode] = useState<'upload' | 'live'>('live')

  // Note state
  const [note, setNote] = useState<NoteResponse | null>(null)
  const [isLoadingNote, setIsLoadingNote] = useState(false)
  const [isGeneratingNote, setIsGeneratingNote] = useState(false)
  const [noteError, setNoteError] = useState<string | null>(null)

  // Fetch note for visit
  const fetchNote = useCallback(async () => {
    if (!id) return
    setIsLoadingNote(true)
    try {
      const noteData = await getNote(id)
      setNote(noteData)
    } catch (err) {
      // Note might not exist yet, which is fine
      setNote(null)
    } finally {
      setIsLoadingNote(false)
    }
  }, [id])

  // Callback when transcription completes
  const handleTranscriptionComplete = useCallback(() => {
    if (id) {
      fetchVisit(id)
    }
  }, [id, fetchVisit])

  // Handle note generation
  const handleGenerateNote = async () => {
    if (!id) return
    setIsGeneratingNote(true)
    setNoteError(null)
    try {
      await generateNote(id)
      // Fetch the generated note
      await fetchNote()
      toast.success('SOAP note generated successfully')
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to generate note'
      setNoteError(errorMsg)
      toast.error(errorMsg)
    } finally {
      setIsGeneratingNote(false)
    }
  }

  // Handle note update
  const handleNoteUpdate = (updatedNote: NoteResponse) => {
    setNote(updatedNote)
  }

  // Transcription status polling
  const {
    isPolling,
    error: transcriptionError,
    startPolling,
  } = useTranscriptionPolling({
    visitId: currentVisit?.audio_file_path ? id ?? null : null,
    enabled: Boolean(currentVisit?.audio_file_path),
    onComplete: handleTranscriptionComplete,
  })

  useEffect(() => {
    if (id) {
      fetchVisit(id)
      fetchNote()
    }
    return () => clearCurrentVisit()
  }, [id, fetchVisit, fetchNote, clearCurrentVisit])

  // Handle retry transcription
  const handleRetryTranscription = async () => {
    if (!id) return
    setIsRetrying(true)
    try {
      await retryTranscription(id)
      startPolling()
      await fetchVisit(id)
    } catch (err) {
      console.error('Failed to retry transcription:', err)
    } finally {
      setIsRetrying(false)
    }
  }

  const handleDelete = async () => {
    if (!id) return
    setIsDeleting(true)
    const success = await deleteVisit(id)
    if (success) {
      toast.success('Visit deleted successfully')
      navigate('/dashboard')
    } else {
      toast.error('Failed to delete visit')
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
      toast.success('Audio uploaded successfully')
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to upload audio'
      setUploadError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsUploading(false)
    }
  }

  // Handle live transcription complete
  const handleLiveTranscriptionComplete = async (transcript: string) => {
    // Note: Do not log transcript content (PHI)
    toast.success('Live transcription completed')
    // Refresh visit data to show transcript
    if (id) {
      await fetchVisit(id)
      await fetchNote()
    }
  }

  const handleLiveTranscriptionError = (errorMsg: string) => {
    console.error('Live transcription error:', errorMsg)
    setUploadError(errorMsg)
    toast.error(errorMsg)
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
      <div className="mb-6">
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
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
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
            currentVisit.audio_file_path || currentVisit.transcript
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

          {currentVisit.audio_file_path || currentVisit.transcript ? (
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
                      {currentVisit.is_live_transcription
                        ? 'Live transcription complete'
                        : 'Audio uploaded successfully'}
                    </p>
                    <p className="text-sm text-green-600">
                      Duration: {formatDuration(currentVisit.audio_duration_seconds || 0)}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Recording Mode Toggle */}
              <div className="flex items-center justify-center gap-1 rounded-lg bg-gray-100 p-1">
                <button
                  onClick={() => setRecordingMode('live')}
                  className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                    recordingMode === 'live'
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Live Transcription
                </button>
                <button
                  onClick={() => setRecordingMode('upload')}
                  className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                    recordingMode === 'upload'
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Record & Upload
                </button>
              </div>

              {/* Mode Description */}
              <p className="text-center text-xs text-gray-500">
                {recordingMode === 'live'
                  ? 'Real-time transcription as you speak - see text appear instantly'
                  : 'Record audio first, then upload for transcription'}
              </p>

              {/* Recorder Component */}
              {recordingMode === 'live' ? (
                <LiveRecorder
                  visitId={id!}
                  onComplete={handleLiveTranscriptionComplete}
                  onError={handleLiveTranscriptionError}
                />
              ) : (
                <AudioRecorder
                  onRecordingComplete={handleRecordingComplete}
                  isUploading={isUploading}
                  maxDurationSeconds={3600}
                />
              )}
            </div>
          )}
        </Card>

        {/* Transcript */}
        <Card
          title="Transcript"
          subtitle={
            currentVisit.transcription_status === 'completed'
              ? 'Transcription complete'
              : currentVisit.transcription_status === 'transcribing' || isPolling
              ? 'Transcription in progress...'
              : currentVisit.transcription_status === 'failed'
              ? 'Transcription failed'
              : 'Awaiting audio upload'
          }
        >
          {/* Transcription in progress */}
          {(currentVisit.transcription_status === 'transcribing' || isPolling) && (
            <div className="flex flex-col items-center justify-center py-8">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary-500 border-t-transparent"></div>
              <p className="mt-4 text-sm text-gray-600">
                Transcribing audio with AI...
              </p>
              <p className="mt-1 text-xs text-gray-400">
                This may take a few moments
              </p>
            </div>
          )}

          {/* Transcription failed */}
          {currentVisit.transcription_status === 'failed' && !isPolling && (
            <div className="rounded-md bg-red-50 p-4">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-red-100">
                  <svg
                    className="h-5 w-5 text-red-600"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
                <div className="flex-1">
                  <p className="font-medium text-red-800">Transcription failed</p>
                  <p className="mt-1 text-sm text-red-600">
                    {transcriptionError || 'An error occurred during transcription. Please try again.'}
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="mt-3"
                    onClick={handleRetryTranscription}
                    isLoading={isRetrying}
                  >
                    Retry Transcription
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Transcription completed */}
          {currentVisit.transcription_status === 'completed' && currentVisit.transcript && (
            <div className="prose max-w-none">
              <div className="whitespace-pre-wrap rounded-lg bg-gray-50 p-4 text-gray-700">
                {currentVisit.transcript}
              </div>
            </div>
          )}

          {/* Pending - no audio yet */}
          {currentVisit.transcription_status === 'pending' && !currentVisit.audio_file_path && (
            <div className="rounded-md bg-gray-50 p-4 text-center">
              <p className="text-sm text-gray-500">
                Transcript will appear here after audio is uploaded and transcribed
              </p>
            </div>
          )}

          {/* Pending - audio uploaded, waiting for transcription to start */}
          {currentVisit.transcription_status === 'pending' && currentVisit.audio_file_path && !isPolling && (
            <div className="rounded-md bg-yellow-50 p-4 text-center">
              <p className="text-sm text-yellow-700">
                Audio uploaded. Transcription will begin shortly...
              </p>
            </div>
          )}
        </Card>

        {/* SOAP Note */}
        <Card
          title="SOAP Note"
          subtitle={
            note
              ? `Status: ${note.status}`
              : isGeneratingNote
              ? 'Generating note...'
              : 'Generate a structured SOAP note from the transcript'
          }
        >
          {/* Error message */}
          {noteError && (
            <div className="mb-4 rounded-md bg-red-50 p-3">
              <p className="text-sm text-red-700">{noteError}</p>
            </div>
          )}

          {/* Loading note */}
          {isLoadingNote && !note && (
            <div className="flex items-center justify-center py-8">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-t-transparent"></div>
            </div>
          )}

          {/* Generating note */}
          {isGeneratingNote && (
            <div className="flex flex-col items-center justify-center py-8">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary-500 border-t-transparent"></div>
              <p className="mt-4 text-sm text-gray-600">
                Generating SOAP note with AI...
              </p>
              <p className="mt-1 text-xs text-gray-400">
                This may take a moment
              </p>
            </div>
          )}

          {/* Note exists - show editor */}
          {note && !isGeneratingNote && (
            <NoteEditor
              note={note}
              visitId={id!}
              onUpdate={handleNoteUpdate}
            />
          )}

          {/* No note yet - show generate button */}
          {!note && !isLoadingNote && !isGeneratingNote && (
            <div className="rounded-md bg-gray-50 p-6 text-center">
              {currentVisit.transcription_status === 'completed' && currentVisit.transcript ? (
                <div>
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
                  <p className="mt-3 text-sm text-gray-600">
                    Transcript is ready. Generate a structured SOAP note.
                  </p>
                  <Button
                    className="mt-4"
                    onClick={handleGenerateNote}
                  >
                    Generate SOAP Note
                  </Button>
                </div>
              ) : (
                <div>
                  <svg
                    className="mx-auto h-12 w-12 text-gray-300"
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
                  <p className="mt-3 text-sm text-gray-500">
                    SOAP note can be generated after transcription is complete
                  </p>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Actions */}
        <Card padding="sm">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-gray-500">
              Created: {formatDate(currentVisit.created_at)}
            </p>
            <Button
              variant="danger"
              size="sm"
              onClick={() => setShowDeleteConfirm(true)}
              className="w-full sm:w-auto"
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
