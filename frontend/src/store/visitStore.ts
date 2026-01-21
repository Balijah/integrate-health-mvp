/**
 * Visit store using Zustand.
 *
 * Manages visit state and CRUD operations.
 */

import { create } from 'zustand'

import {
  createVisit as createVisitApi,
  deleteVisit as deleteVisitApi,
  getVisit as getVisitApi,
  getVisits as getVisitsApi,
  CreateVisitRequest,
  VisitResponse,
} from '../api/visits'
import { getErrorMessage } from '../api/client'

/**
 * Visit state interface.
 */
interface VisitState {
  /** List of visits */
  visits: VisitResponse[]
  /** Currently selected visit */
  currentVisit: VisitResponse | null
  /** Total number of visits */
  total: number
  /** Current page limit */
  limit: number
  /** Current page offset */
  offset: number
  /** Loading state */
  isLoading: boolean
  /** Error message */
  error: string | null
}

/**
 * Visit actions interface.
 */
interface VisitActions {
  /** Fetch list of visits */
  fetchVisits: (limit?: number, offset?: number) => Promise<void>
  /** Fetch a single visit by ID */
  fetchVisit: (id: string) => Promise<void>
  /** Create a new visit */
  createVisit: (data: CreateVisitRequest) => Promise<VisitResponse | null>
  /** Delete a visit */
  deleteVisit: (id: string) => Promise<boolean>
  /** Clear current visit */
  clearCurrentVisit: () => void
  /** Clear error */
  clearError: () => void
}

/**
 * Combined visit store type.
 */
type VisitStore = VisitState & VisitActions

/**
 * Initial state values.
 */
const initialState: VisitState = {
  visits: [],
  currentVisit: null,
  total: 0,
  limit: 20,
  offset: 0,
  isLoading: false,
  error: null,
}

/**
 * Visit store.
 */
export const useVisitStore = create<VisitStore>((set, get) => ({
  ...initialState,

  fetchVisits: async (limit = 20, offset = 0) => {
    set({ isLoading: true, error: null })
    try {
      const response = await getVisitsApi(limit, offset)
      set({
        visits: response.items,
        total: response.total,
        limit: response.limit,
        offset: response.offset,
        isLoading: false,
      })
    } catch (error) {
      set({
        isLoading: false,
        error: getErrorMessage(error),
      })
    }
  },

  fetchVisit: async (id: string) => {
    set({ isLoading: true, error: null })
    try {
      const visit = await getVisitApi(id)
      set({
        currentVisit: visit,
        isLoading: false,
      })
    } catch (error) {
      set({
        isLoading: false,
        error: getErrorMessage(error),
      })
    }
  },

  createVisit: async (data: CreateVisitRequest) => {
    set({ isLoading: true, error: null })
    try {
      const visit = await createVisitApi(data)
      // Add to beginning of list
      set((state) => ({
        visits: [visit, ...state.visits],
        total: state.total + 1,
        isLoading: false,
      }))
      return visit
    } catch (error) {
      set({
        isLoading: false,
        error: getErrorMessage(error),
      })
      return null
    }
  },

  deleteVisit: async (id: string) => {
    set({ isLoading: true, error: null })
    try {
      await deleteVisitApi(id)
      // Remove from list
      set((state) => ({
        visits: state.visits.filter((v) => v.id !== id),
        total: state.total - 1,
        currentVisit:
          state.currentVisit?.id === id ? null : state.currentVisit,
        isLoading: false,
      }))
      return true
    } catch (error) {
      set({
        isLoading: false,
        error: getErrorMessage(error),
      })
      return false
    }
  },

  clearCurrentVisit: () => {
    set({ currentVisit: null })
  },

  clearError: () => {
    set({ error: null })
  },
}))
