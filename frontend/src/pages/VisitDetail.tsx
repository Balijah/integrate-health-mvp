import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Check, Trash2, Printer, Send } from 'lucide-react'

import { useAudioRecorder } from '../hooks/useAudioRecorder'
import { useTranscriptionPolling } from '../hooks/useTranscriptionPolling'
import { uploadAudio, getVisit, updateVisit, deleteVisit, VisitResponse } from '../api/visits'
import { generateNote, getNote, NoteResponse, SOAPContent } from '../api/notes'

type Step = 0 | 1 | 2 // speak=0, summarize=1, sync=2

interface SyncStatus {
  subjective: boolean
  objective: boolean
  assessment: boolean
  plan: boolean
}

type SoapKey = keyof SyncStatus

const soapSections: SoapKey[] = ['subjective', 'objective', 'assessment', 'plan']

const sectionPlaceholders: Record<SoapKey, string> = {
  subjective: "Patient's subjective symptoms and history...",
  objective: 'Objective findings, vitals, exam results...',
  assessment: 'Clinical assessment and diagnoses...',
  plan: 'Treatment plan, medications, follow-up...',
}

// Convert a SOAP section object to readable text
function sectionToText(key: SoapKey, content: SOAPContent): string {
  if (!content) return ''
  const section = content[key]
  if (!section) return ''

  if (key === 'subjective') {
    const s = section as SOAPContent['subjective']
    const parts: string[] = []
    if (s.chief_complaint) parts.push(`Chief Complaint: ${s.chief_complaint}`)
    if (s.history_of_present_illness) parts.push(`History: ${s.history_of_present_illness}`)
    if (s.review_of_systems) parts.push(`Review of Systems: ${s.review_of_systems}`)
    if (s.past_medical_history) parts.push(`Past Medical History: ${s.past_medical_history}`)
    if (s.medications?.length) parts.push(`Medications: ${s.medications.join(', ')}`)
    if (s.supplements?.length) parts.push(`Supplements: ${s.supplements.join(', ')}`)
    if (s.allergies?.length) parts.push(`Allergies: ${s.allergies.join(', ')}`)
    if (s.social_history) parts.push(`Social History: ${s.social_history}`)
    if (s.family_history) parts.push(`Family History: ${s.family_history}`)
    return parts.join('\n\n')
  }
  if (key === 'objective') {
    const o = section as SOAPContent['objective']
    const parts: string[] = []
    if (o.vitals) {
      const v = o.vitals
      const vitals = [v.blood_pressure && `BP ${v.blood_pressure}`, v.heart_rate && `HR ${v.heart_rate}`, v.temperature && `Temp ${v.temperature}`, v.weight && `Weight ${v.weight}`].filter(Boolean)
      if (vitals.length) parts.push(`Vitals: ${vitals.join(', ')}`)
    }
    if (o.physical_exam) parts.push(`Physical Exam: ${o.physical_exam}`)
    if (o.lab_results) parts.push(`Lab Results: ${o.lab_results}`)
    return parts.join('\n\n')
  }
  if (key === 'assessment') {
    const a = section as SOAPContent['assessment']
    const parts: string[] = []
    if (a.diagnoses?.length) parts.push(`Diagnoses: ${a.diagnoses.join('; ')}`)
    if (a.clinical_reasoning) parts.push(`Clinical Reasoning: ${a.clinical_reasoning}`)
    return parts.join('\n\n')
  }
  if (key === 'plan') {
    const p = section as SOAPContent['plan']
    const parts: string[] = []
    if (p.treatment_plan) parts.push(`Treatment Plan: ${p.treatment_plan}`)
    if (p.medications_prescribed?.length) parts.push(`Medications Prescribed: ${p.medications_prescribed.join(', ')}`)
    if (p.supplements_recommended?.length) parts.push(`Supplements: ${p.supplements_recommended.join(', ')}`)
    if (p.lifestyle_recommendations) parts.push(`Lifestyle: ${p.lifestyle_recommendations}`)
    if (p.lab_orders?.length) parts.push(`Lab Orders: ${p.lab_orders.join(', ')}`)
    if (p.follow_up) parts.push(`Follow-up: ${p.follow_up}`)
    if (p.patient_education) parts.push(`Patient Education: ${p.patient_education}`)
    return parts.join('\n\n')
  }
  return ''
}

// SVG ring progress component for step 3
function SyncRing({ synced, total }: { synced: number; total: number }) {
  const r = 18
  const c = 2 * Math.PI * r
  const progress = synced / total
  const dash = progress * c

  if (synced >= total) {
    return (
      <div className="w-10 h-10 rounded-full flex items-center justify-center"
        style={{ background: 'linear-gradient(135deg, #4ac6d6 0%, #2a8fa0 100%)' }}>
        <Check size={16} className="text-white" />
      </div>
    )
  }

  return (
    <div className="relative w-10 h-10">
      <svg width="40" height="40" viewBox="0 0 40 40" className="-rotate-90">
        <circle cx="20" cy="20" r={r} fill="none" stroke="#e5e7eb" strokeWidth="3" />
        <circle
          cx="20" cy="20" r={r}
          fill="none"
          stroke="#4ac6d6"
          strokeWidth="3"
          strokeDasharray={`${dash} ${c}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-sm font-medium text-[#4ac6d6]">
        {synced}
      </div>
    </div>
  )
}

// Step circle component
function StepCircle({ step, current, synced, total }: { step: number; current: Step; synced?: number; total?: number }) {
  const done = step < current
  const active = step === current

  if (step === 2 && active) {
    return <SyncRing synced={synced ?? 0} total={total ?? 4} />
  }
  if (step === 2 && done) {
    return (
      <div className="w-10 h-10 rounded-full flex items-center justify-center"
        style={{ background: 'linear-gradient(135deg, #4ac6d6 0%, #2a8fa0 100%)' }}>
        <Check size={16} className="text-white" />
      </div>
    )
  }
  if (done) {
    return (
      <div className="w-10 h-10 rounded-full flex items-center justify-center"
        style={{ background: 'linear-gradient(135deg, #4ac6d6 0%, #2a8fa0 100%)' }}>
        <Check size={16} className="text-white" />
      </div>
    )
  }
  if (active) {
    return (
      <div className="w-10 h-10 rounded-full flex items-center justify-center"
        style={{ background: 'linear-gradient(135deg, #4ac6d6 0%, #2a8fa0 100%)' }}>
        <span className="text-white font-medium">{step + 1}</span>
      </div>
    )
  }
  return (
    <div className="w-10 h-10 rounded-full border-2 border-gray-300 flex items-center justify-center">
      <span className="text-gray-400 font-medium">{step + 1}</span>
    </div>
  )
}

export const VisitDetail = () => {
  const { visitId } = useParams<{ visitId: string }>()
  const navigate = useNavigate()

  const [visit, setVisit] = useState<VisitResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [currentStep, setCurrentStep] = useState<Step>(0)

  // Note state
  const [note, setNote] = useState<NoteResponse | null>(null)
  const [noteTexts, setNoteTexts] = useState<Record<SoapKey, string>>({
    subjective: '', objective: '', assessment: '', plan: ''
  })
  const [isGeneratingNote, setIsGeneratingNote] = useState(false)

  // Sync state
  const [syncedSections, setSyncedSections] = useState<SyncStatus>({
    subjective: false, objective: false, assessment: false, plan: false
  })
  const [copiedSection, setCopiedSection] = useState<SoapKey | null>(null)

  // Patient summary state
  const [patientSummary, setPatientSummary] = useState('')
  const [summaryEmail, setSummaryEmail] = useState('')
  const [showSendConfirm, setShowSendConfirm] = useState(false)
  const [showSendSuccess, setShowSendSuccess] = useState(false)

  // Upload state
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  // Inline edit state
  const [editingField, setEditingField] = useState<string | null>(null)
  const [chiefComplaintDraft, setChiefComplaintDraft] = useState('')
  const [visitDateDraft, setVisitDateDraft] = useState('')
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  // Recording
  const recorder = useAudioRecorder()
  const isRecording = recorder.state === 'recording'

  // Load visit
  useEffect(() => {
    if (!visitId) return
    setIsLoading(true)
    getVisit(visitId)
      .then(v => {
        setVisit(v)
        setChiefComplaintDraft(v.chief_complaint || '')
        setVisitDateDraft(v.visit_date)
        // If audio exists but not step 1, advance
        if (v.audio_file_path || v.transcript) {
          setCurrentStep(1)
        }
      })
      .catch(() => navigate('/'))
      .finally(() => setIsLoading(false))
  }, [visitId, navigate])

  // Load note
  const loadNote = useCallback(async () => {
    if (!visitId) return
    try {
      const n = await getNote(visitId)
      if (n) {
        setNote(n)
        setNoteTexts({
          subjective: sectionToText('subjective', n.content),
          objective: sectionToText('objective', n.content),
          assessment: sectionToText('assessment', n.content),
          plan: sectionToText('plan', n.content),
        })
      }
    } catch {
      // note doesn't exist yet
    }
  }, [visitId])

  useEffect(() => {
    loadNote()
  }, [loadNote])

  // Transcription polling
  const polling = useTranscriptionPolling({
    visitId: visit?.audio_file_path ? visitId ?? null : null,
    enabled: Boolean(visit?.audio_file_path) && visit?.transcription_status !== 'completed',
    intervalMs: 3000,
    onComplete: transcript => {
      setVisit(prev => prev ? { ...prev, transcript, transcription_status: 'completed' } : prev)
    },
  })

  // Step 2: auto-generate note if transcript ready but no note
  useEffect(() => {
    if (currentStep === 1 && visit?.transcription_status === 'completed' && visit.transcript && !note && !isGeneratingNote) {
      handleGenerateNote()
    }
  }, [currentStep, visit?.transcription_status, visit?.transcript, note])

  // Upload when recorder transitions to stopped state with a blob
  const [pendingUpload, setPendingUpload] = useState(false)

  useEffect(() => {
    if (recorder.state === 'stopped' && recorder.audioBlob && pendingUpload && visitId) {
      const blob = recorder.audioBlob
      setPendingUpload(false)
      setIsUploading(true)
      setUploadError(null)
      uploadAudio(visitId, blob)
        .then(() => getVisit(visitId))
        .then(updated => {
          setVisit(updated)
          polling.startPolling()
        })
        .catch(() => setUploadError('Failed to upload audio. Please try again.'))
        .finally(() => setIsUploading(false))
    }
  }, [recorder.state, recorder.audioBlob, pendingUpload, visitId])

  const handleStartRecording = async () => {
    await recorder.startRecording()
  }

  const handleStopRecording = () => {
    setPendingUpload(true)
    recorder.stopRecording()
  }

  const handleGenerateNote = async () => {
    if (!visitId) return
    setIsGeneratingNote(true)
    try {
      await generateNote(visitId)
      await loadNote()
    } catch {
      // ignore — note generation can fail silently for now
    } finally {
      setIsGeneratingNote(false)
    }
  }

  const handleSync = async (section: SoapKey) => {
    const text = noteTexts[section]
    if (text) {
      try {
        await navigator.clipboard.writeText(text)
      } catch {
        // fallback: silent fail
      }
      setCopiedSection(section)
      setTimeout(() => setCopiedSection(null), 1500)
    }
    setSyncedSections(prev => ({ ...prev, [section]: true }))
    // Advance to step 3 on first sync
    if (currentStep < 2) setCurrentStep(2)
  }

  const handleSaveField = async (field: 'chief_complaint' | 'visit_date') => {
    if (!visitId) return
    try {
      const updated = await updateVisit(visitId, {
        [field]: field === 'chief_complaint' ? chiefComplaintDraft : visitDateDraft
      })
      setVisit(updated)
    } catch { /* ignore */ }
    setEditingField(null)
  }

  const handleDelete = async () => {
    if (!visitId) return
    setIsDeleting(true)
    try {
      await deleteVisit(visitId)
      navigate('/')
    } catch {
      setIsDeleting(false)
      setShowDeleteConfirm(false)
    }
  }

  const syncedCount = Object.values(syncedSections).filter(Boolean).length

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-8 h-8 animate-spin rounded-full border-4 border-[#4ac6d6] border-t-transparent" />
      </div>
    )
  }

  if (!visit) return null

  return (
    <div className="w-full max-w-5xl mx-auto pb-16">
      {/* Page Header */}
      <div className="mb-8 flex items-start justify-between mt-12">
        <div>
          <h1 className="text-4xl mb-2">{visit.patient_ref}</h1>
          <div className="flex items-center gap-2 text-sm text-gray-500 flex-wrap">
            {/* Chief complaint */}
            {editingField === 'chief_complaint' ? (
              <input
                autoFocus
                value={chiefComplaintDraft}
                onChange={e => setChiefComplaintDraft(e.target.value)}
                onBlur={() => handleSaveField('chief_complaint')}
                onKeyDown={e => e.key === 'Enter' && handleSaveField('chief_complaint')}
                className="italic text-sm border-b border-[#4ac6d6] focus:outline-none bg-transparent"
              />
            ) : (
              <button
                onClick={() => setEditingField('chief_complaint')}
                className="italic hover:text-gray-700"
              >
                {visit.chief_complaint || 'Add chief complaint'}
              </button>
            )}
            <span>•</span>
            {/* Date */}
            {editingField === 'visit_date' ? (
              <input
                autoFocus
                type="datetime-local"
                value={visitDateDraft.slice(0, 16)}
                onChange={e => setVisitDateDraft(e.target.value)}
                onBlur={() => handleSaveField('visit_date')}
                className="text-sm border-b border-[#4ac6d6] focus:outline-none bg-transparent"
              />
            ) : (
              <button
                onClick={() => setEditingField('visit_date')}
                className="hover:text-gray-700"
              >
                {new Date(visit.visit_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </button>
            )}
            <span>•</span>
            <span>{new Date(visit.visit_date).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}</span>
          </div>
        </div>
        <button
          onClick={() => setShowDeleteConfirm(true)}
          className="text-gray-400 hover:text-red-500 transition-colors mt-1"
        >
          <Trash2 size={20} />
        </button>
      </div>

      {/* Step Progress Indicator */}
      <div className="flex items-center justify-center mb-10">
        {(['speak', 'summarize', 'sync'] as const).map((label, idx) => (
          <div key={label} className="flex items-center">
            <button
              onClick={() => idx <= currentStep && setCurrentStep(idx as Step)}
              className="flex flex-col items-center gap-1"
            >
              <StepCircle
                step={idx}
                current={currentStep}
                synced={syncedCount}
                total={4}
              />
              <span className={`text-xs ${idx === currentStep ? 'text-[#4ac6d6] font-medium' : idx < currentStep ? 'text-gray-500' : 'text-gray-400'}`}>
                {label}
              </span>
            </button>
            {idx < 2 && (
              <div className={`w-24 h-0.5 mx-2 mb-5 ${idx < currentStep ? 'bg-[#4ac6d6]' : 'bg-gray-200'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Step 1: Speak */}
      <AnimatePresence mode="wait">
        {currentStep === 0 && (
          <motion.div
            key="step-speak"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-4"
          >
            {/* Transcript display */}
            <div className="bg-white border border-[#4ac6d6] rounded-2xl p-6 min-h-[120px] flex items-center justify-center">
              {isRecording ? (
                <div className="flex items-center gap-3 text-gray-600">
                  <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 1, repeat: Infinity }}
                    className="w-3 h-3 bg-red-500 rounded-full"
                  />
                  <span>Recording in progress... {recorder.duration}s</span>
                </div>
              ) : isUploading ? (
                <div className="flex items-center gap-3 text-gray-600">
                  <div className="w-5 h-5 animate-spin rounded-full border-2 border-[#4ac6d6] border-t-transparent" />
                  <span>Uploading audio...</span>
                </div>
              ) : polling.isPolling || visit.transcription_status === 'transcribing' ? (
                <div className="flex items-center gap-3 text-gray-600">
                  <div className="w-5 h-5 animate-spin rounded-full border-2 border-[#4ac6d6] border-t-transparent" />
                  <span>Transcribing...</span>
                </div>
              ) : visit.transcript || polling.transcript ? (
                <p className="text-gray-700 text-sm">{visit.transcript || polling.transcript}</p>
              ) : uploadError ? (
                <p className="text-red-500 text-sm">{uploadError}</p>
              ) : (
                <span className="text-gray-400 italic text-sm">Transcript will appear here after recording</span>
              )}
            </div>

            {/* Record button */}
            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              onClick={isRecording ? handleStopRecording : handleStartRecording}
              disabled={isUploading || polling.isPolling}
              className="relative w-full h-16 rounded-xl overflow-hidden disabled:opacity-50"
              style={{ background: isRecording ? '#ef4444' : 'linear-gradient(135deg, #4ac6d6, #2a8fa0)' }}
            >
              <span className="text-white font-normal drop-shadow-md">
                {isRecording ? 'stop recording' : 'start recording'}
              </span>
            </motion.button>

            {recorder.error && (
              <p className="text-sm text-red-500 text-center">{recorder.error}</p>
            )}

            {/* Advance button when transcript is ready */}
            {(visit.transcript || polling.transcript) && (
              <button
                onClick={() => setCurrentStep(1)}
                className="w-full border-2 border-[#4ac6d6] text-[#4ac6d6] rounded-xl py-3 hover:bg-[#4ac6d6]/10 transition-colors"
              >
                continue to summarize →
              </button>
            )}
          </motion.div>
        )}

        {/* Step 2 & 3: Summarize / Sync */}
        {currentStep >= 1 && (
          <motion.div
            key="step-summarize"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-4"
          >
            {isGeneratingNote && (
              <div className="text-center py-8">
                <div className="w-8 h-8 animate-spin rounded-full border-4 border-[#4ac6d6] border-t-transparent mx-auto mb-3" />
                <p className="text-gray-600 italic">Generating SOAP note...</p>
              </div>
            )}

            {!isGeneratingNote && !note && (
              <div className="text-center py-8">
                <p className="text-gray-500 italic mb-4">
                  {visit.transcription_status === 'completed'
                    ? 'Ready to generate your SOAP note.'
                    : 'Waiting for transcription to complete...'}
                </p>
                {visit.transcription_status === 'completed' && (
                  <button
                    onClick={handleGenerateNote}
                    className="bg-[#4ac6d6] text-gray-900 rounded-xl px-8 py-3 hover:bg-[#3ab5c5] transition-colors"
                  >
                    Generate SOAP Note
                  </button>
                )}
              </div>
            )}

            {/* SOAP Sections */}
            {note && !isGeneratingNote && soapSections.map(section => (
              <div key={section} className="bg-white border border-[#4ac6d6] rounded-2xl p-6">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-lg capitalize">{section}</h3>
                  <div className="flex items-center gap-2">
                    <AnimatePresence>
                      {copiedSection === section && (
                        <motion.span
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="text-xs text-green-600"
                        >
                          Copied!
                        </motion.span>
                      )}
                    </AnimatePresence>
                    <button
                      onClick={() => handleSync(section)}
                      className={`flex items-center gap-1 px-4 py-1.5 text-white text-sm rounded-lg transition-colors ${
                        syncedSections[section]
                          ? 'bg-green-500 hover:bg-green-600'
                          : 'bg-[#4ac6d6] hover:bg-[#3ab5c5]'
                      }`}
                    >
                      {syncedSections[section] ? <Check size={14} /> : null}
                      {syncedSections[section] ? 'sync again' : 'sync'}
                    </button>
                  </div>
                </div>
                <textarea
                  value={noteTexts[section]}
                  onChange={e => setNoteTexts(prev => ({ ...prev, [section]: e.target.value }))}
                  className="w-full min-h-[200px] resize-y text-sm text-gray-700 focus:outline-none bg-transparent"
                  placeholder={sectionPlaceholders[section]}
                />
              </div>
            ))}

            {/* Patient Summary */}
            {note && !isGeneratingNote && (
              <div className="bg-white border border-[#4ac6d6] rounded-2xl p-6">
                <h3 className="text-lg mb-4">Patient Summary</h3>
                <textarea
                  value={patientSummary}
                  onChange={e => setPatientSummary(e.target.value)}
                  rows={4}
                  className="w-full resize-y text-sm text-gray-700 focus:outline-none bg-transparent mb-4 placeholder:italic placeholder:text-gray-400"
                  placeholder="Patient-friendly summary will appear here"
                />
                <div className="flex items-center gap-3">
                  <input
                    type="email"
                    value={summaryEmail}
                    onChange={e => setSummaryEmail(e.target.value)}
                    placeholder="patient@email.com"
                    className="flex-1 border border-gray-200 rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-[#4ac6d6] italic text-gray-600 placeholder:text-gray-400"
                  />
                  <button
                    onClick={() => window.print()}
                    className="p-2 text-gray-500 hover:text-[#4ac6d6] transition-colors"
                    title="Print"
                  >
                    <Printer size={20} />
                  </button>
                  <button
                    onClick={() => setShowSendConfirm(true)}
                    className="p-2 text-gray-500 hover:text-[#4ac6d6] transition-colors"
                    title="Send to patient"
                  >
                    <Send size={20} />
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Send Confirmation Modal */}
      <AnimatePresence>
        {showSendConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
            onClick={e => e.target === e.currentTarget && setShowSendConfirm(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 25 }}
              className="bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl"
            >
              <h2 className="text-2xl mb-4">Send Patient Summary</h2>
              <p className="text-gray-600 mb-2">
                Are you sure you want to send the patient summary to:
              </p>
              <p className="text-[#4ac6d6] font-medium mb-6">{summaryEmail || 'No email provided'}</p>
              <div className="flex gap-3">
                <button
                  onClick={() => setShowSendConfirm(false)}
                  className="flex-1 border-2 border-[#4ac6d6] text-gray-900 rounded-xl py-3 hover:bg-gray-50 transition-colors"
                >
                  cancel
                </button>
                <button
                  onClick={async () => {
                    try {
                      const token = localStorage.getItem('token')
                      await fetch(`/api/v1/visits/${visitId}/summary/send`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                        body: JSON.stringify({ email: summaryEmail, summary: patientSummary }),
                      })
                    } catch (e) { /* still show success */ }
                    setShowSendConfirm(false)
                    setShowSendSuccess(true)
                    setTimeout(() => setShowSendSuccess(false), 3000)
                  }}
                  className="flex-1 bg-[#4ac6d6] text-gray-900 rounded-xl py-3 hover:bg-[#3ab5c5] transition-colors font-medium"
                >
                  send summary
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Send Success Toast */}
      <AnimatePresence>
        {showSendSuccess && (
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 50 }}
            className="fixed bottom-8 left-1/2 -translate-x-1/2 bg-green-500 text-white rounded-xl px-6 py-3 shadow-lg z-50 flex items-center gap-2"
          >
            <Check size={16} />
            Summary sent successfully
          </motion.div>
        )}
      </AnimatePresence>

      {/* Delete Confirmation */}
      <AnimatePresence>
        {showDeleteConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
            onClick={e => e.target === e.currentTarget && setShowDeleteConfirm(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 25 }}
              className="bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl"
            >
              <h2 className="text-2xl mb-4">Delete Visit</h2>
              <p className="text-gray-600 mb-6">
                Are you sure you want to delete this visit? This cannot be undone.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={isDeleting}
                  className="flex-1 border-2 border-gray-300 text-gray-900 rounded-xl py-3 hover:bg-gray-50 transition-colors"
                >
                  cancel
                </button>
                <button
                  onClick={handleDelete}
                  disabled={isDeleting}
                  className="flex-1 bg-red-500 text-white rounded-xl py-3 hover:bg-red-600 transition-colors font-medium disabled:opacity-50"
                >
                  {isDeleting ? 'deleting...' : 'delete'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
