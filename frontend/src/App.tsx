/**
 * Root application component.
 *
 * Sets up routing for the application.
 */

import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'

import { ProtectedRoute } from './components/ProtectedRoute'
import { Dashboard, Login, NewVisit, Register, VisitDetail } from './pages'
import { useAuthStore } from './store/authStore'

export const App = () => {
  const { loadUser, token } = useAuthStore()

  // Load user on app start if token exists
  useEffect(() => {
    if (token) {
      loadUser()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Protected routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/visits/new"
        element={
          <ProtectedRoute>
            <NewVisit />
          </ProtectedRoute>
        }
      />
      <Route
        path="/visits/:id"
        element={
          <ProtectedRoute>
            <VisitDetail />
          </ProtectedRoute>
        }
      />

      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* 404 fallback */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
