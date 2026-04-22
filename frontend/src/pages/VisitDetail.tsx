import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Check, Trash2, Printer, Send } from 'lucide-react'

import { useTranscriptionPolling } from '../hooks/useTranscriptionPolling'
import { getVisit, updateVisit, deleteVisit, retryTranscription, VisitResponse } from '../api/visits'
import { LiveRecorder } from '../components/LiveRecorder/LiveRecorder'
import { TranscriptSegment } from '../hooks/useLiveTranscription'
import { generateNote, getNote, syncSection, NoteResponse } from '../api/notes'

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

// Convert a SOAP section object to readable text.
// Handles both the old schema (chief_complaint, medications, etc.) and
// the new schema (reason_for_visit, current_medications, prescriptions.add/continue, clinical_discussion, etc.)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function sectionToText(key: SoapKey, content: any): string {
  if (!content) return ''
  const section = content[key]
  if (!section) return ''
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const s = section as any
  const parts: string[] = []

  if (key === 'subjective') {
    const rv = s.reason_for_visit || s.chief_complaint
    if (rv) parts.push(`Reason for Visit: ${rv}`)
    if (s.history_of_present_illness) parts.push(`History of Present Illness: ${s.history_of_present_illness}`)
    if (s.review_of_systems) parts.push(`Review of Systems: ${s.review_of_systems}`)
    if (s.past_medical_history) parts.push(`Past Medical History: ${s.past_medical_history}`)
    const meds = s.current_medications ?? s.medications
    if (meds?.length) parts.push(`Current Medications:\n${meds.map((m: string) => `• ${m}`).join('\n')}`)
    const supps = s.current_supplements ?? s.supplements
    if (supps?.length) parts.push(`Current Supplements:\n${supps.map((m: string) => `• ${m}`).join('\n')}`)
    if (s.allergies?.length) parts.push(`Allergies: ${s.allergies.join(', ')}`)
    if (s.social_history) parts.push(`Social History: ${s.social_history}`)
    if (s.family_history) parts.push(`Family History: ${s.family_history}`)
  }

  if (key === 'objective') {
    if (s.vitals) {
      const v = s.vitals
      const vParts = [
        v.blood_pressure && `BP ${v.blood_pressure}`,
        v.heart_rate && `HR ${v.heart_rate}`,
        v.temperature && `Temp ${v.temperature}`,
        v.weight && `Weight ${v.weight}`,
        v.height && `Height ${v.height}`,
        v.bmi && `BMI ${v.bmi}`,
      ].filter(Boolean)
      if (vParts.length) parts.push(`Vitals: ${vParts.join(', ')}`)
    }
    if (s.physical_exam) parts.push(`Physical Exam: ${s.physical_exam}`)
    if (s.lab_results) parts.push(`Lab Results: ${s.lab_results}`)
  }

  if (key === 'assessment') {
    if (s.diagnoses?.length) parts.push(`Diagnoses:\n${s.diagnoses.map((d: string) => `• ${d}`).join('\n')}`)
    // New: clinical_discussion array
    if (s.clinical_discussion?.length) {
      const disc = s.clinical_discussion.map((d: any) => {
        const lines = [`${d.issue}`]
        if (d.findings) lines.push(`  Findings: ${d.findings}`)
        if (d.interpretation) lines.push(`  Assessment: ${d.interpretation}`)
        if (d.plan_summary) lines.push(`  Plan: ${d.plan_summary}`)
        return lines.join('\n')
      }).join('\n\n')
      parts.push(`Clinical Discussion:\n${disc}`)
    }
    if (s.clinical_reasoning) parts.push(`Clinical Reasoning: ${s.clinical_reasoning}`)
  }

  if (key === 'plan') {
    if (s.treatment_plan) parts.push(`Treatment Plan: ${s.treatment_plan}`)
    // New: structured prescriptions
    if (s.prescriptions) {
      if (s.prescriptions.add?.length) parts.push(`New Prescriptions:\n${s.prescriptions.add.map((m: string) => `• ${m}`).join('\n')}`)
      if (s.prescriptions.continue?.length) parts.push(`Continuing Prescriptions:\n${s.prescriptions.continue.map((m: string) => `• ${m}`).join('\n')}`)
      if (s.prescriptions.discontinue?.length) parts.push(`Discontinued Prescriptions:\n${s.prescriptions.discontinue.map((m: string) => `• ${m}`).join('\n')}`)
    } else if (s.medications_prescribed?.length) {
      parts.push(`Medications Prescribed:\n${s.medications_prescribed.map((m: string) => `• ${m}`).join('\n')}`)
    }
    // New: structured supplements
    if (s.supplements && (s.supplements.add || s.supplements.continue || s.supplements.discontinue)) {
      if (s.supplements.add?.length) parts.push(`New Supplements:\n${s.supplements.add.map((m: string) => `• ${m}`).join('\n')}`)
      if (s.supplements.continue?.length) parts.push(`Continuing Supplements:\n${s.supplements.continue.map((m: string) => `• ${m}`).join('\n')}`)
      if (s.supplements.discontinue?.length) parts.push(`Discontinued Supplements:\n${s.supplements.discontinue.map((m: string) => `• ${m}`).join('\n')}`)
    } else if (s.supplements_recommended?.length) {
      parts.push(`Supplements:\n${s.supplements_recommended.map((m: string) => `• ${m}`).join('\n')}`)
    }
    if (s.lab_orders?.length) parts.push(`Lab Orders:\n${s.lab_orders.map((l: string) => `• ${l}`).join('\n')}`)
    if (s.imaging_or_referrals?.length) parts.push(`Imaging / Referrals:\n${s.imaging_or_referrals.map((r: string) => `• ${r}`).join('\n')}`)
    if (s.lifestyle_recommendations) parts.push(`Lifestyle Recommendations: ${s.lifestyle_recommendations}`)
    if (s.follow_up) parts.push(`Follow-up: ${s.follow_up}`)
    if (s.patient_education) parts.push(`Patient Education: ${s.patient_education}`)
  }

  return parts.join('\n\n')
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
  // true once the initial loadNote() attempt for this visit has completed
  const [noteLoadAttempted, setNoteLoadAttempted] = useState(false)

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
  const [isSendingEmail, setIsSendingEmail] = useState(false)
  const [sendEmailError, setSendEmailError] = useState<string | null>(null)

  // Live recording done state (persists even if user navigates back to step 0)
  const [liveRecordingDone, setLiveRecordingDone] = useState(false)
  // Accumulate segments as they arrive (mirrors hook deduplication logic) — bypasses closure staleness
  const liveSegmentsRef = useRef<{ speaker: string; text: string }[]>([])
  const liveLastWasInterimRef = useRef(false)

  const handleLiveTranscript = useCallback((segment: TranscriptSegment) => {
    if (!segment.text) return
    const arr = liveSegmentsRef.current
    const entry = { speaker: segment.speaker, text: segment.text }
    if (!segment.isFinal) {
      if (liveLastWasInterimRef.current && arr.length > 0) {
        arr[arr.length - 1] = entry
      } else {
        arr.push(entry)
      }
      liveLastWasInterimRef.current = true
    } else {
      if (liveLastWasInterimRef.current && arr.length > 0) {
        arr[arr.length - 1] = entry
      } else {
        arr.push(entry)
      }
      liveLastWasInterimRef.current = false
    }
  }, [])

  // Upload state
  const [isRetrying, setIsRetrying] = useState(false)

  // Inline edit state
  const [editingField, setEditingField] = useState<string | null>(null)
  const [chiefComplaintDraft, setChiefComplaintDraft] = useState('')
  const [visitDateDraft, setVisitDateDraft] = useState('')
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  // Load visit
  useEffect(() => {
    if (!visitId) return
    // Reset all visit-specific state when navigating to a new visit
    setNote(null)
    setNoteTexts({ subjective: '', objective: '', assessment: '', plan: '' })
    setSyncedSections({ subjective: false, objective: false, assessment: false, plan: false })
    setCurrentStep(0)
    setPatientSummary('')
    setSummaryEmail('')
    setChiefComplaintDraft('')
    setVisitDateDraft('')
    setLiveRecordingDone(false)
    liveSegmentsRef.current = []
    liveLastWasInterimRef.current = false
    setNoteLoadAttempted(false)
    setIsLoading(true)
    getVisit(visitId)
      .then(v => {
        setVisit(v)
        setChiefComplaintDraft(v.chief_complaint || '')
        setVisitDateDraft(v.visit_date)
        // Advance to summarize step only if transcription is in progress or done
        if ((v.audio_file_path || v.transcript) && v.transcription_status !== 'failed') {
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
        setSyncedSections({
          subjective: Boolean(n.synced_sections?.subjective),
          objective: Boolean(n.synced_sections?.objective),
          assessment: Boolean(n.synced_sections?.assessment),
          plan: Boolean(n.synced_sections?.plan),
        })
      }
    } catch {
      // note doesn't exist yet
    } finally {
      setNoteLoadAttempted(true)
    }
  }, [visitId])

  useEffect(() => {
    loadNote()
  }, [loadNote])

  const handleRetryTranscription = async () => {
    if (!visitId) return
    setIsRetrying(true)
    try {
      await retryTranscription(visitId)
      setVisit(prev => prev ? { ...prev, transcription_status: 'transcribing', transcript: null } : prev)
      setCurrentStep(1)
      polling.startPolling()
    } catch {
      // ignore — visit will still show failed state
    } finally {
      setIsRetrying(false)
    }
  }

  // Transcription polling
  const polling = useTranscriptionPolling({
    visitId: visit?.audio_file_path ? visitId ?? null : null,
    enabled: Boolean(visit?.audio_file_path) && visit?.transcription_status !== 'completed',
    intervalMs: 3000,
    onComplete: transcript => {
      setVisit(prev => prev ? { ...prev, transcript, transcription_status: 'completed' } : prev)
    },
    onError: () => {
      setVisit(prev => prev ? { ...prev, transcription_status: 'failed' } : prev)
    },
  })

  // Step 2: auto-generate note if transcript ready but no note
  // Waits for noteLoadAttempted to avoid racing with the initial loadNote() call
  useEffect(() => {
    if (currentStep === 1 && !note && !isGeneratingNote && noteLoadAttempted) {
      const batchReady = visit?.transcription_status === 'completed' && Boolean(visit?.transcript)
      if (batchReady || liveRecordingDone) {
        handleGenerateNote()
      }
    }
  }, [currentStep, visit?.transcription_status, visit?.transcript, note, liveRecordingDone, noteLoadAttempted])

  const handleLiveComplete = useCallback(async (_transcript: string) => {
    setLiveRecordingDone(true)

    // Poll DB to get the authoritative saved transcript (for the plain-text fallback)
    if (!visitId) return
    let attempts = 0
    const poll = async () => {
      try {
        const fresh = await getVisit(visitId)
        setVisit(fresh)
        if (!fresh.transcript && attempts < 12) { attempts++; setTimeout(poll, 2000) }
      } catch {
        if (attempts < 12) { attempts++; setTimeout(poll, 2000) }
      }
    }
    poll()
  }, [visitId])

  const handleGenerateNote = async () => {
    if (!visitId) return
    setIsGeneratingNote(true)
    try {
      await generateNote(visitId)
    } catch {
      // ignore — may fail if note already exists
    }
    // always load the note after attempting generation, whether just created or pre-existing
    try {
      await loadNote()
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
    // Persist sync to database and notify sidebar to refresh
    if (visitId && note) {
      try {
        await syncSection(visitId, note.id, section)
        window.dispatchEvent(new CustomEvent('visits-updated'))
      } catch {
        // non-critical: local state already updated
      }
    }
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
            {liveRecordingDone ? (
              /* Live recording just finished — show diarized segments or DB fallback */
              <div className="space-y-3">
                <p className="text-sm text-green-600">Recording complete. Transcript saved.</p>
                {liveSegmentsRef.current.length > 0 ? (
                  /* Diarized view — segments with speaker labels */
                  <div className="bg-white border border-gray-200 rounded-2xl p-4 max-h-80 overflow-y-auto space-y-3">
                    {liveSegmentsRef.current.map((seg, i) => (
                      <div key={i} className="flex gap-3">
                        <span className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full h-fit mt-0.5 ${
                          seg.speaker === 'provider'
                            ? 'bg-[#4ac6d6]/20 text-[#2a8fa0]'
                            : 'bg-gray-100 text-gray-600'
                        }`}>
                          {seg.speaker === 'provider' ? 'Provider' : 'Patient'}
                        </span>
                        <p className="text-sm text-gray-700 leading-relaxed">{seg.text}</p>
                      </div>
                    ))}
                  </div>
                ) : visit.transcript ? (
                  /* Plain text fallback from DB */
                  <div className="bg-white border border-gray-200 rounded-2xl p-4 max-h-80 overflow-y-auto">
                    <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{visit.transcript}</p>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 italic text-center py-2">Loading transcript...</p>
                )}
              </div>
            ) : visit.transcript ? (
              /* Transcript already in DB (re-loaded visit) — show it directly */
              <div className="space-y-3">
                <p className="text-sm text-green-600">Recording complete. Transcript saved.</p>
                <div className="bg-white border border-gray-200 rounded-2xl p-4 max-h-80 overflow-y-auto">
                  <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{visit.transcript}</p>
                </div>
              </div>
            ) : (
              /* Live recorder — handles its own transcript display, controls, and status */
              <LiveRecorder
                visitId={visitId!}
                onComplete={handleLiveComplete}
                onTranscript={handleLiveTranscript}
              />
            )}

            {/* Batch retry fallback — only shown when visit has audio but transcription failed */}
            {(visit.transcription_status === 'failed' || polling.status === 'failed') && visit.audio_file_path && (
              <div className="text-center">
                <p className="text-red-500 text-sm mb-3 italic">
                  {polling.error || 'Transcription returned no text. Please try again — if this persists, the audio may not have been captured correctly.'}
                </p>
                <button
                  onClick={handleRetryTranscription}
                  disabled={isRetrying}
                  className="bg-[#4ac6d6] text-gray-900 rounded-xl px-6 py-2 text-sm hover:bg-[#3ab5c5] transition-colors disabled:opacity-50"
                >
                  {isRetrying ? 'retrying...' : 'retry transcription'}
                </button>
              </div>
            )}

            {/* Advance button when transcript is ready (batch or live) */}
            {(liveRecordingDone || visit.transcript || polling.transcript) && (
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
                {visit.transcription_status === 'failed' ? (
                  <>
                    <p className="text-red-500 italic mb-4">
                      {polling.error || 'Transcription failed. The audio may not have been captured correctly.'}
                    </p>
                    <button
                      onClick={handleRetryTranscription}
                      disabled={isRetrying}
                      className="bg-[#4ac6d6] text-gray-900 rounded-xl px-8 py-3 hover:bg-[#3ab5c5] transition-colors disabled:opacity-50"
                    >
                      {isRetrying ? 'retrying...' : 'retry transcription'}
                    </button>
                  </>
                ) : (
                  <>
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
                  </>
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
                {sendEmailError && (
                  <p className="text-sm text-red-500 mb-2">{sendEmailError}</p>
                )}
                <div className="flex items-center gap-3">
                  <input
                    type="email"
                    value={summaryEmail}
                    onChange={e => { setSummaryEmail(e.target.value); if (sendEmailError) setSendEmailError(null) }}
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
                    onClick={() => {
                      if (!summaryEmail.trim()) {
                        setSendEmailError('Please enter a patient email address.')
                        return
                      }
                      if (!patientSummary.trim()) {
                        setSendEmailError('Please enter a summary before sending.')
                        return
                      }
                      setSendEmailError(null)
                      setShowSendConfirm(true)
                    }}
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
              <p className="text-[#4ac6d6] font-medium mb-6">{summaryEmail}</p>
              {sendEmailError && (
                <p className="text-sm text-red-500 mb-4">{sendEmailError}</p>
              )}
              <div className="flex gap-3">
                <button
                  onClick={() => { setShowSendConfirm(false); setSendEmailError(null) }}
                  disabled={isSendingEmail}
                  className="flex-1 border-2 border-[#4ac6d6] text-gray-900 rounded-xl py-3 hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  cancel
                </button>
                <button
                  disabled={isSendingEmail}
                  onClick={async () => {
                    setIsSendingEmail(true)
                    setSendEmailError(null)
                    try {
                      const token = localStorage.getItem('token')
                      const res = await fetch(`/api/v1/visits/${visitId}/summary/send`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                        body: JSON.stringify({ email: summaryEmail, summary: patientSummary }),
                      })
                      if (!res.ok) {
                        const data = await res.json().catch(() => ({}))
                        setSendEmailError(data?.detail || 'Failed to send email. Please try again.')
                        return
                      }
                      setShowSendConfirm(false)
                      setShowSendSuccess(true)
                      setTimeout(() => setShowSendSuccess(false), 3000)
                    } catch {
                      setSendEmailError('Failed to send email. Please try again.')
                    } finally {
                      setIsSendingEmail(false)
                    }
                  }}
                  className="flex-1 bg-[#4ac6d6] text-gray-900 rounded-xl py-3 hover:bg-[#3ab5c5] transition-colors font-medium disabled:opacity-50"
                >
                  {isSendingEmail ? 'sending...' : 'send summary'}
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
