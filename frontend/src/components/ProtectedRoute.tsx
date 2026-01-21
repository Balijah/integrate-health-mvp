/**
 * Protected route wrapper component.
 *
 * Redirects unauthenticated users to login page.
 */

import { ReactNode, useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAuthStore } from '../store/authStore'

interface ProtectedRouteProps {
  children: ReactNode
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const location = useLocation()
  const { isAuthenticated, isLoading, loadUser, token } = useAuthStore()

  // Try to load user on mount if we have a token
  useEffect(() => {
    if (token && !isAuthenticated) {
      loadUser()
    }
  }, [token, isAuthenticated, loadUser])

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-t-transparent"></div>
          <p className="mt-2 text-sm text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated && !token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
