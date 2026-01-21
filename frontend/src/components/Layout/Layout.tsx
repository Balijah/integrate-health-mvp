/**
 * Main application layout component.
 *
 * Provides consistent header and navigation for authenticated pages.
 */

import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { useAuthStore } from '../../store/authStore'
import { Button } from '../common/Button'

interface LayoutProps {
  children: ReactNode
}

interface NavLinkProps {
  to: string
  children: ReactNode
}

const NavLink = ({ to, children }: NavLinkProps) => {
  const location = useLocation()
  const isActive = location.pathname === to

  return (
    <Link
      to={to}
      className={`
        rounded-md px-3 py-2 text-sm font-medium transition-colors
        ${
          isActive
            ? 'bg-primary-100 text-primary-700'
            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
        }
      `}
    >
      {children}
    </Link>
  )
}

export const Layout = ({ children }: LayoutProps) => {
  const { user, logout } = useAuthStore()

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            {/* Logo and nav */}
            <div className="flex items-center gap-8">
              <Link to="/dashboard" className="flex items-center">
                <span className="text-xl font-bold text-gray-900">
                  Integrate Health
                </span>
              </Link>

              <nav className="hidden md:flex md:items-center md:gap-1">
                <NavLink to="/dashboard">Dashboard</NavLink>
                <NavLink to="/visits/new">New Visit</NavLink>
              </nav>
            </div>

            {/* User menu */}
            <div className="flex items-center gap-4">
              <span className="hidden text-sm text-gray-600 sm:block">
                {user?.full_name}
              </span>
              <Button variant="ghost" size="sm" onClick={logout}>
                Sign out
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {children}
      </main>
    </div>
  )
}
