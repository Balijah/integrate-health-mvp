import { useState, FormEvent, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'

import { useAuthStore } from '../store/authStore'
import logoLoginImg from '../assets/logo-login.png'

export const Login = () => {
  const navigate = useNavigate()
  const { login, isLoading, error, clearError, isAuthenticated } = useAuthStore()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/')
    }
  }, [isAuthenticated, navigate])

  useEffect(() => {
    return () => clearError()
  }, [clearError])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const success = await login({ email, password })
    if (success) {
      navigate('/')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f8f9fa] px-4"
      style={{ background: 'linear-gradient(135deg, #f8f9fa 0%, #e8f9fb 100%)' }}
    >
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <img
            src={logoLoginImg}
            alt="integrate health"
            className="max-w-[240px] object-contain"
          />
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl p-8 shadow-lg border border-[#4ac6d6]/20">
          <h1 className="text-3xl text-center mb-2">welcome back</h1>
          <p className="text-center italic text-gray-500 mb-8">Sign in to access your portal</p>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-6">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full border-2 border-[#4ac6d6] rounded-xl px-4 py-3 text-gray-900 placeholder:italic placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#4ac6d6]/30"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full border-2 border-[#4ac6d6] rounded-xl px-4 py-3 pr-12 text-gray-900 placeholder:italic placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#4ac6d6]/30"
                  placeholder="Enter your password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(s => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#4ac6d6] hover:text-[#3ab5c5]"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => window.location.href = '/forgot-password'}
                className="text-sm text-[#4ac6d6] hover:text-[#3ab5c5]"
              >
                forgot password?
              </button>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-[#4ac6d6] hover:bg-[#3ab5c5] text-gray-900 font-medium rounded-xl py-3 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'signing in...' : 'sign in'}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Don't have an account?{' '}
            <Link to="/register" className="text-[#4ac6d6] hover:text-[#3ab5c5]">
              Register here
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
