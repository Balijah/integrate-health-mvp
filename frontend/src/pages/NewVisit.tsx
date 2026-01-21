/**
 * New Visit page component.
 *
 * Form for creating a new patient visit.
 */

import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button, Card, Input, Layout } from '../components'
import { useVisitStore } from '../store/visitStore'

export const NewVisit = () => {
  const navigate = useNavigate()
  const { createVisit, isLoading, error, clearError } = useVisitStore()

  const [patientRef, setPatientRef] = useState('')
  const [visitDate, setVisitDate] = useState('')
  const [visitTime, setVisitTime] = useState('')
  const [chiefComplaint, setChiefComplaint] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    clearError()

    // Combine date and time
    const dateTime = visitTime
      ? `${visitDate}T${visitTime}:00`
      : `${visitDate}T12:00:00`

    const visit = await createVisit({
      patient_ref: patientRef,
      visit_date: dateTime,
      chief_complaint: chiefComplaint || undefined,
    })

    if (visit) {
      navigate(`/visits/${visit.id}`)
    }
  }

  return (
    <Layout>
      <div className="mx-auto max-w-2xl">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">New Visit</h1>
          <p className="mt-1 text-sm text-gray-500">
            Create a new patient visit record
          </p>
        </div>

        <Card>
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="rounded-md bg-red-50 p-4">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <Input
              label="Patient Reference"
              value={patientRef}
              onChange={(e) => setPatientRef(e.target.value)}
              placeholder="e.g., PT-001 or PATIENT-ABC"
              helperText="Non-PHI identifier for the patient"
              required
            />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="Visit Date"
                type="date"
                value={visitDate}
                onChange={(e) => setVisitDate(e.target.value)}
                required
              />

              <Input
                label="Visit Time"
                type="time"
                value={visitTime}
                onChange={(e) => setVisitTime(e.target.value)}
                helperText="Optional"
              />
            </div>

            <div>
              <label
                htmlFor="chiefComplaint"
                className="block text-sm font-medium text-gray-700"
              >
                Chief Complaint
              </label>
              <textarea
                id="chiefComplaint"
                value={chiefComplaint}
                onChange={(e) => setChiefComplaint(e.target.value)}
                rows={3}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                placeholder="Main reason for the visit"
              />
              <p className="mt-1 text-sm text-gray-500">
                Brief description of why the patient is here
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 border-t border-gray-200 pt-6">
              <Button
                type="button"
                variant="secondary"
                onClick={() => navigate('/dashboard')}
              >
                Cancel
              </Button>
              <Button type="submit" isLoading={isLoading}>
                Create Visit
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </Layout>
  )
}
