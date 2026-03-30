import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut } from 'lucide-react'

import { useAuthStore } from '../store/authStore'

interface ToggleProps {
  checked: boolean
  onChange: (v: boolean) => void
}

function Toggle({ checked, onChange }: ToggleProps) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative w-12 h-6 rounded-full transition-colors ${checked ? 'bg-[#4ac6d6]' : 'bg-gray-200'}`}
    >
      <span
        className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${checked ? 'translate-x-6' : 'translate-x-0'}`}
      />
    </button>
  )
}

export const Settings = () => {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const nameParts = (user?.full_name || '').split(' ')
  const [firstName, setFirstName] = useState(nameParts[0] || '')
  const [lastName, setLastName] = useState(nameParts.slice(1).join(' ') || '')
  const [email, setEmail] = useState(user?.email || '')
  const [phone, setPhone] = useState('')
  const [saved, setSaved] = useState(false)

  const [notifications, setNotifications] = useState({
    email: true,
    push: false,
    sms: false,
    marketing: false,
  })

  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="w-full max-w-2xl">
      <div className="mb-8 mt-12">
        <h1 className="text-4xl mb-1">Settings</h1>
        <p className="italic text-gray-500">Manage your account and preferences</p>
      </div>

      {/* Profile Information */}
      <div className="mb-12">
        <h2 className="text-2xl mb-6">Profile Information</h2>
        <div className="bg-white border border-[#4ac6d6] rounded-2xl p-8 shadow-md">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
              <input
                value={firstName}
                onChange={e => setFirstName(e.target.value)}
                className="w-full border-2 border-[#4ac6d6] rounded-xl px-4 py-3 text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#4ac6d6]/30"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
              <input
                value={lastName}
                onChange={e => setLastName(e.target.value)}
                className="w-full border-2 border-[#4ac6d6] rounded-xl px-4 py-3 text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#4ac6d6]/30"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full border-2 border-[#4ac6d6] rounded-xl px-4 py-3 text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#4ac6d6]/30"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
              <input
                type="tel"
                value={phone}
                onChange={e => {
                  // Format as (xxx) xxx-xxxx
                  const digits = e.target.value.replace(/\D/g, '').slice(0, 10)
                  let formatted = digits
                  if (digits.length >= 4) formatted = `(${digits.slice(0, 3)}) ${digits.slice(3)}`
                  if (digits.length >= 7) formatted = `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`
                  setPhone(formatted)
                }}
                placeholder="(555) 555-5555"
                className="w-full border-2 border-[#4ac6d6] rounded-xl px-4 py-3 text-gray-900 placeholder:italic placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#4ac6d6]/30"
              />
            </div>
          </div>
          <button
            onClick={handleSave}
            className={`px-8 py-3 rounded-xl font-medium transition-colors ${
              saved
                ? 'bg-green-500 text-white'
                : 'bg-[#4ac6d6] hover:bg-[#3ab5c5] text-gray-900'
            }`}
          >
            {saved ? '✓ saved' : 'save changes'}
          </button>
        </div>
      </div>

      {/* Notification Preferences */}
      <div className="mb-12">
        <h2 className="text-2xl mb-6">Notification Preferences</h2>
        <div className="bg-white border border-[#4ac6d6] rounded-2xl p-8 shadow-md space-y-6">
          {[
            { key: 'email' as const, label: 'Email notifications', desc: 'Receive updates via email' },
            { key: 'push' as const, label: 'Push notifications', desc: 'Browser push notifications' },
            { key: 'sms' as const, label: 'SMS notifications', desc: 'Text message alerts' },
            { key: 'marketing' as const, label: 'Marketing emails', desc: 'Product updates and tips' },
          ].map(({ key, label, desc }) => (
            <div key={key} className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-gray-900">{label}</div>
                <div className="text-xs italic text-gray-500">{desc}</div>
              </div>
              <Toggle
                checked={notifications[key]}
                onChange={v => setNotifications(prev => ({ ...prev, [key]: v }))}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Sign out */}
      <button
        onClick={handleLogout}
        className="flex items-center gap-2 text-red-500 hover:text-red-700 transition-colors"
      >
        <LogOut size={16} />
        <span className="text-sm">sign out</span>
      </button>
    </div>
  )
}
