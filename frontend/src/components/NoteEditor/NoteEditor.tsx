/**
 * SOAP Note Editor component.
 *
 * Displays and allows editing of structured SOAP notes with collapsible sections.
 */

import { useState, useCallback } from 'react'

import { Button } from '../common/Button'
import { SOAPContent, NoteResponse, updateNote, exportNote } from '../../api/notes'

interface NoteEditorProps {
  /** Note data */
  note: NoteResponse
  /** Visit ID */
  visitId: string
  /** Callback when note is updated */
  onUpdate?: (note: NoteResponse) => void
  /** Whether editing is disabled */
  disabled?: boolean
}

interface SectionProps {
  title: string
  isOpen: boolean
  onToggle: () => void
  children: React.ReactNode
}

/**
 * Collapsible section component.
 */
const Section = ({ title, isOpen, onToggle, children }: SectionProps) => (
  <div className="border border-gray-200 rounded-lg overflow-hidden">
    <button
      onClick={onToggle}
      className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
    >
      <span className="font-semibold text-gray-900">{title}</span>
      <svg
        className={`h-5 w-5 text-gray-500 transition-transform ${
          isOpen ? 'rotate-180' : ''
        }`}
        viewBox="0 0 20 20"
        fill="currentColor"
      >
        <path
          fillRule="evenodd"
          d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
          clipRule="evenodd"
        />
      </svg>
    </button>
    {isOpen && <div className="p-4 space-y-4">{children}</div>}
  </div>
)

/**
 * Text field component for editing.
 */
const TextField = ({
  label,
  value,
  onChange,
  multiline = false,
  disabled = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  multiline?: boolean
  disabled?: boolean
}) => (
  <div>
    <label className="block text-sm font-medium text-gray-700 mb-1">
      {label}
    </label>
    {multiline ? (
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        rows={3}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
      />
    ) : (
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
      />
    )}
  </div>
)

/**
 * List field component for editing arrays.
 */
const ListField = ({
  label,
  items,
  onChange,
  disabled = false,
}: {
  label: string
  items: string[]
  onChange: (items: string[]) => void
  disabled?: boolean
}) => {
  const addItem = () => {
    onChange([...items, ''])
  }

  const updateItem = (index: number, value: string) => {
    const newItems = [...items]
    newItems[index] = value
    onChange(newItems)
  }

  const removeItem = (index: number) => {
    onChange(items.filter((_, i) => i !== index))
  }

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
      </label>
      <div className="space-y-2">
        {items.map((item, index) => (
          <div key={index} className="flex gap-2">
            <input
              type="text"
              value={item}
              onChange={(e) => updateItem(index, e.target.value)}
              disabled={disabled}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-gray-100"
            />
            {!disabled && (
              <button
                onClick={() => removeItem(index)}
                className="px-2 py-1 text-red-600 hover:text-red-800"
              >
                <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
            )}
          </div>
        ))}
        {!disabled && (
          <button
            onClick={addItem}
            className="text-sm text-primary-600 hover:text-primary-800"
          >
            + Add item
          </button>
        )}
      </div>
      {items.length === 0 && (
        <p className="text-sm text-gray-400 italic">No items</p>
      )}
    </div>
  )
}

export const NoteEditor = ({
  note,
  visitId,
  onUpdate,
  disabled = false,
}: NoteEditorProps) => {
  const [content, setContent] = useState<SOAPContent>(note.content)
  const [status, setStatus] = useState(note.status)
  const [isSaving, setIsSaving] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [hasChanges, setHasChanges] = useState(false)

  // Section open states
  const [openSections, setOpenSections] = useState({
    subjective: true,
    objective: true,
    assessment: true,
    plan: true,
  })

  const toggleSection = (section: keyof typeof openSections) => {
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }))
  }

  // Update content helper
  const updateContent = useCallback(
    <K extends keyof SOAPContent>(
      section: K,
      field: keyof SOAPContent[K],
      value: unknown
    ) => {
      setContent((prev) => ({
        ...prev,
        [section]: {
          ...prev[section],
          [field]: value,
        },
      }))
      setHasChanges(true)
    },
    []
  )

  // Save changes
  const handleSave = async () => {
    setIsSaving(true)
    setSaveError(null)

    try {
      const updated = await updateNote(visitId, note.id, { content, status })
      setHasChanges(false)
      onUpdate?.(updated)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setIsSaving(false)
    }
  }

  // Mark as reviewed
  const handleMarkReviewed = async () => {
    setIsSaving(true)
    setSaveError(null)

    try {
      const updated = await updateNote(visitId, note.id, {
        content,
        status: 'reviewed',
      })
      setStatus('reviewed')
      setHasChanges(false)
      onUpdate?.(updated)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to update status')
    } finally {
      setIsSaving(false)
    }
  }

  // Export note
  const handleExport = async (format: 'markdown' | 'text' | 'json') => {
    setIsExporting(true)

    try {
      const result = await exportNote(visitId, note.id, format)

      // Copy to clipboard
      await navigator.clipboard.writeText(result.content)
      alert(`Note copied to clipboard as ${format}!`)
    } catch (err) {
      alert('Failed to export note')
    } finally {
      setIsExporting(false)
    }
  }

  // Copy to clipboard
  const handleCopy = async () => {
    try {
      const result = await exportNote(visitId, note.id, 'markdown')
      await navigator.clipboard.writeText(result.content)
      alert('Note copied to clipboard!')
    } catch (err) {
      alert('Failed to copy note')
    }
  }

  return (
    <div className="space-y-4">
      {/* Status bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${
              status === 'draft'
                ? 'bg-yellow-100 text-yellow-800'
                : status === 'reviewed'
                ? 'bg-green-100 text-green-800'
                : 'bg-blue-100 text-blue-800'
            }`}
          >
            {status}
          </span>
          {hasChanges && (
            <span className="text-sm text-orange-600">Unsaved changes</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleCopy}
            disabled={isExporting}
          >
            Copy
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => handleExport('markdown')}
            disabled={isExporting}
          >
            Export
          </Button>
          {status === 'draft' && (
            <Button
              size="sm"
              onClick={handleMarkReviewed}
              isLoading={isSaving}
              disabled={disabled}
            >
              Mark Reviewed
            </Button>
          )}
          {hasChanges && (
            <Button
              size="sm"
              onClick={handleSave}
              isLoading={isSaving}
              disabled={disabled}
            >
              Save
            </Button>
          )}
        </div>
      </div>

      {saveError && (
        <div className="rounded-md bg-red-50 p-3">
          <p className="text-sm text-red-700">{saveError}</p>
        </div>
      )}

      {/* Subjective Section */}
      <Section
        title="Subjective"
        isOpen={openSections.subjective}
        onToggle={() => toggleSection('subjective')}
      >
        <TextField
          label="Chief Complaint"
          value={content.subjective.chief_complaint}
          onChange={(v) => updateContent('subjective', 'chief_complaint', v)}
          disabled={disabled}
        />
        <TextField
          label="History of Present Illness"
          value={content.subjective.history_of_present_illness}
          onChange={(v) => updateContent('subjective', 'history_of_present_illness', v)}
          multiline
          disabled={disabled}
        />
        <TextField
          label="Review of Systems"
          value={content.subjective.review_of_systems}
          onChange={(v) => updateContent('subjective', 'review_of_systems', v)}
          multiline
          disabled={disabled}
        />
        <TextField
          label="Past Medical History"
          value={content.subjective.past_medical_history}
          onChange={(v) => updateContent('subjective', 'past_medical_history', v)}
          multiline
          disabled={disabled}
        />
        <ListField
          label="Current Medications"
          items={content.subjective.medications}
          onChange={(v) => updateContent('subjective', 'medications', v)}
          disabled={disabled}
        />
        <ListField
          label="Current Supplements"
          items={content.subjective.supplements}
          onChange={(v) => updateContent('subjective', 'supplements', v)}
          disabled={disabled}
        />
        <ListField
          label="Allergies"
          items={content.subjective.allergies}
          onChange={(v) => updateContent('subjective', 'allergies', v)}
          disabled={disabled}
        />
        <TextField
          label="Social History"
          value={content.subjective.social_history}
          onChange={(v) => updateContent('subjective', 'social_history', v)}
          multiline
          disabled={disabled}
        />
        <TextField
          label="Family History"
          value={content.subjective.family_history}
          onChange={(v) => updateContent('subjective', 'family_history', v)}
          multiline
          disabled={disabled}
        />
      </Section>

      {/* Objective Section */}
      <Section
        title="Objective"
        isOpen={openSections.objective}
        onToggle={() => toggleSection('objective')}
      >
        <div className="grid grid-cols-2 gap-4">
          <TextField
            label="Blood Pressure"
            value={content.objective.vitals.blood_pressure}
            onChange={(v) =>
              setContent((prev) => ({
                ...prev,
                objective: {
                  ...prev.objective,
                  vitals: { ...prev.objective.vitals, blood_pressure: v },
                },
              }))
            }
            disabled={disabled}
          />
          <TextField
            label="Heart Rate"
            value={content.objective.vitals.heart_rate}
            onChange={(v) =>
              setContent((prev) => ({
                ...prev,
                objective: {
                  ...prev.objective,
                  vitals: { ...prev.objective.vitals, heart_rate: v },
                },
              }))
            }
            disabled={disabled}
          />
          <TextField
            label="Temperature"
            value={content.objective.vitals.temperature}
            onChange={(v) =>
              setContent((prev) => ({
                ...prev,
                objective: {
                  ...prev.objective,
                  vitals: { ...prev.objective.vitals, temperature: v },
                },
              }))
            }
            disabled={disabled}
          />
          <TextField
            label="Weight"
            value={content.objective.vitals.weight}
            onChange={(v) =>
              setContent((prev) => ({
                ...prev,
                objective: {
                  ...prev.objective,
                  vitals: { ...prev.objective.vitals, weight: v },
                },
              }))
            }
            disabled={disabled}
          />
        </div>
        <TextField
          label="Physical Exam"
          value={content.objective.physical_exam}
          onChange={(v) => updateContent('objective', 'physical_exam', v)}
          multiline
          disabled={disabled}
        />
        <TextField
          label="Lab Results"
          value={content.objective.lab_results}
          onChange={(v) => updateContent('objective', 'lab_results', v)}
          multiline
          disabled={disabled}
        />
      </Section>

      {/* Assessment Section */}
      <Section
        title="Assessment"
        isOpen={openSections.assessment}
        onToggle={() => toggleSection('assessment')}
      >
        <ListField
          label="Diagnoses"
          items={content.assessment.diagnoses}
          onChange={(v) => updateContent('assessment', 'diagnoses', v)}
          disabled={disabled}
        />
        <TextField
          label="Clinical Reasoning"
          value={content.assessment.clinical_reasoning}
          onChange={(v) => updateContent('assessment', 'clinical_reasoning', v)}
          multiline
          disabled={disabled}
        />
      </Section>

      {/* Plan Section */}
      <Section
        title="Plan"
        isOpen={openSections.plan}
        onToggle={() => toggleSection('plan')}
      >
        <TextField
          label="Treatment Plan"
          value={content.plan.treatment_plan}
          onChange={(v) => updateContent('plan', 'treatment_plan', v)}
          multiline
          disabled={disabled}
        />
        <ListField
          label="Medications Prescribed"
          items={content.plan.medications_prescribed}
          onChange={(v) => updateContent('plan', 'medications_prescribed', v)}
          disabled={disabled}
        />
        <ListField
          label="Supplements Recommended"
          items={content.plan.supplements_recommended}
          onChange={(v) => updateContent('plan', 'supplements_recommended', v)}
          disabled={disabled}
        />
        <TextField
          label="Lifestyle Recommendations"
          value={content.plan.lifestyle_recommendations}
          onChange={(v) => updateContent('plan', 'lifestyle_recommendations', v)}
          multiline
          disabled={disabled}
        />
        <ListField
          label="Lab Orders"
          items={content.plan.lab_orders}
          onChange={(v) => updateContent('plan', 'lab_orders', v)}
          disabled={disabled}
        />
        <TextField
          label="Follow-up"
          value={content.plan.follow_up}
          onChange={(v) => updateContent('plan', 'follow_up', v)}
          disabled={disabled}
        />
        <TextField
          label="Patient Education"
          value={content.plan.patient_education}
          onChange={(v) => updateContent('plan', 'patient_education', v)}
          multiline
          disabled={disabled}
        />
      </Section>

      {/* Metadata */}
      <div className="text-sm text-gray-500 border-t pt-4">
        <p>Generated: {new Date(content.metadata.generated_at).toLocaleString()}</p>
        <p>Model: {content.metadata.model_version}</p>
      </div>
    </div>
  )
}
