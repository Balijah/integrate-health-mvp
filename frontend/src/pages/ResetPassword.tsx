import { useState, FormEvent } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { apiClient } from '../api/client'
import logoLoginImg from '../assets/logo-login.png'

export const ResetPassword = () => {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    setIsLoading(true)
    try {
      await apiClient.post('/api/v1/auth/reset-password', {
        token,
        new_password: password,
      })
      setSuccess(true)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to reset password. The link may have expired.')
    } finally {
      setIsLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#f8f9fa] px-4"
        style={{ background: 'linear-gradient(135deg, #f8f9fa 0%, #e8f9fb 100%)' }}>
        <div className="w-full max-w-md text-center">
          <img src={logoLoginImg} alt="integrate health" className="max-w-[240px] object-contain mx-auto mb-8" />
          <div className="bg-white rounded-2xl p-8 shadow-lg border border-[#4ac6d6]/20">
            <h1 className="text-2xl mb-4">Invalid Reset Link</h1>
            <p className="text-gray-500 italic mb-6">This password reset link is invalid or has expired.</p>
            <Link to="/login" className="text-[#4ac6d6] hover:text-[#3ab5c5]">Back to login</Link>
          </div>
        </div>
      </div>
    )
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#f8f9fa] px-4"
        style={{ background: 'linear-gradient(135deg, #f8f9fa 0%, #e8f9fb 100%)' }}>
        <div className="w-full max-w-md text-center">
          <img src={logoLoginImg} alt="integrate health" className="max-w-[240px] object-contain mx-auto mb-8" />
          <div className="bg-white rounded-2xl p-8 shadow-lg border border-[#4ac6d6]/20">
            <h1 className="text-2xl mb-4">Password Reset!</h1>
            <p className="text-gray-500 italic mb-6">Your password has been updated. You can now sign in.</p>
            <button onClick={() => navigate('/login')}
              className="bg-[#4ac6d6] hover:bg-[#3ab5c5] text-gray-900 font-medium rounded-xl px-8 py-3 transition-colors">
              sign in
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f8f9fa] px-4"
      style={{ background: 'linear-gradient(135deg, #f8f9fa 0%, #e8f9fb 100%)' }}>
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <img src={logoLoginImg} alt="integrate health" className="max-w-[240px] object-contain" />
        </div>
        <div className="bg-white rounded-2xl p-8 shadow-lg border border-[#4ac6d6]/20">
          <h1 className="text-3xl text-center mb-2">reset password</h1>
          <p className="text-center italic text-gray-500 mb-8">Enter your new password</p>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-6">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
              <div className="relative">
                <input type={showPassword ? 'text' : 'password'} required value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full border-2 border-[#4ac6d6] rounded-xl px-4 py-3 pr-12 text-gray-900 placeholder:italic placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#4ac6d6]/30"
                  placeholder="At least 8 characters" />
                <button type="button" onClick={() => setShowPassword(s => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#4ac6d6] hover:text-[#3ab5c5]">
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
              <input type="password" required value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                className="w-full border-2 border-[#4ac6d6] rounded-xl px-4 py-3 text-gray-900 placeholder:italic placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#4ac6d6]/30"
                placeholder="Confirm your password" />
            </div>
            <button type="submit" disabled={isLoading}
              className="w-full bg-[#4ac6d6] hover:bg-[#3ab5c5] text-gray-900 font-medium rounded-xl py-3 transition-colors disabled:opacity-50">
              {isLoading ? 'resetting...' : 'reset password'}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            <Link to="/login" className="text-[#4ac6d6] hover:text-[#3ab5c5]">Back to login</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
