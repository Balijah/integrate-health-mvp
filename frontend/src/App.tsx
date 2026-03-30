import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'

import { ProtectedRoute } from './components/ProtectedRoute'
import { Layout } from './components/Layout/Layout'
import { Login } from './pages/Login'
import { Register } from './pages/Register'
import { Dashboard } from './pages/Dashboard'
import { VisitDetail } from './pages/VisitDetail'
import { PatientsList } from './pages/PatientsList'
import { Settings } from './pages/Settings'
import { useAuthStore } from './store/authStore'

export const App = () => {
  const { loadUser, token } = useAuthStore()

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

      {/* Protected routes — all wrapped in Layout (nested routing) */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="patients" element={<PatientsList />} />
        <Route path="visits/:visitId" element={<VisitDetail />} />
        <Route path="settings" element={<Settings />} />
      </Route>

      {/* Legacy redirects */}
      <Route path="/dashboard" element={<Navigate to="/" replace />} />
      <Route path="/visits/new" element={<Navigate to="/" replace />} />

      {/* 404 fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
