/**
 * Main application layout component.
 *
 * Provides consistent header and navigation for authenticated pages.
 */

import { ReactNode, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { useAuthStore } from '../../store/authStore'
import { Button } from '../common/Button'

interface LayoutProps {
  children: ReactNode
}

interface NavLinkProps {
  to: string
  children: ReactNode
  onClick?: () => void
}

const NavLink = ({ to, children, onClick }: NavLinkProps) => {
  const location = useLocation()
  const isActive = location.pathname === to

  return (
    <Link
      to={to}
      onClick={onClick}
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const closeMobileMenu = () => setMobileMenuOpen(false)

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
            <div className="flex items-center gap-2 sm:gap-4">
              <span className="hidden text-sm text-gray-600 sm:block">
                {user?.full_name}
              </span>
              <Button variant="ghost" size="sm" onClick={logout}>
                Sign out
              </Button>
              {/* Mobile menu button */}
              <button
                type="button"
                className="md:hidden inline-flex items-center justify-center rounded-md p-2 text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                aria-expanded={mobileMenuOpen}
              >
                <span className="sr-only">Open main menu</span>
                {mobileMenuOpen ? (
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : (
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-gray-200">
            <div className="space-y-1 px-4 py-3">
              <NavLink to="/dashboard" onClick={closeMobileMenu}>Dashboard</NavLink>
              <NavLink to="/visits/new" onClick={closeMobileMenu}>New Visit</NavLink>
            </div>
          </div>
        )}
      </header>

      {/* Main content */}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {children}
      </main>
    </div>
  )
}
