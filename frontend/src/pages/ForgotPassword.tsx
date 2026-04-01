import { useState, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '../api/client'
import logoLoginImg from '../assets/logo-login.png'

export const ForgotPassword = () => {
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      await apiClient.post('/api/v1/auth/forgot-password', { email })
    } catch { /* always show success to prevent enumeration */ }
    setIsLoading(false)
    setSubmitted(true)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f8f9fa] px-4"
      style={{ background: 'linear-gradient(135deg, #f8f9fa 0%, #e8f9fb 100%)' }}>
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <img src={logoLoginImg} alt="integrate health" className="max-w-[240px] object-contain" />
        </div>
        <div className="bg-white rounded-2xl p-8 shadow-lg border border-[#4ac6d6]/20">
          {submitted ? (
            <div className="text-center">
              <h1 className="text-3xl mb-4">check your email</h1>
              <p className="italic text-gray-500 mb-6">
                If an account with that email exists, we've sent a password reset link.
              </p>
              <Link to="/login" className="text-[#4ac6d6] hover:text-[#3ab5c5]">Back to login</Link>
            </div>
          ) : (
            <>
              <h1 className="text-3xl text-center mb-2">forgot password?</h1>
              <p className="text-center italic text-gray-500 mb-8">Enter your email and we'll send a reset link</p>
              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                    className="w-full border-2 border-[#4ac6d6] rounded-xl px-4 py-3 text-gray-900 placeholder:italic placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#4ac6d6]/30"
                    placeholder="you@example.com" />
                </div>
                <button type="submit" disabled={isLoading}
                  className="w-full bg-[#4ac6d6] hover:bg-[#3ab5c5] text-gray-900 font-medium rounded-xl py-3 transition-colors disabled:opacity-50">
                  {isLoading ? 'sending...' : 'send reset link'}
                </button>
              </form>
              <p className="text-center text-sm text-gray-500 mt-6">
                <Link to="/login" className="text-[#4ac6d6] hover:text-[#3ab5c5]">Back to login</Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
