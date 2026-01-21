import { Routes, Route } from 'react-router-dom'

export const App = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        <Route path="/" element={<HomePage />} />
      </Routes>
    </div>
  )
}

const HomePage = () => {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900">
          Integrate Health MVP
        </h1>
        <p className="mt-4 text-lg text-gray-600">
          HIPAA-compliant AI assistant for functional medicine documentation
        </p>
        <div className="mt-8 rounded-lg bg-white p-6 shadow-md">
          <p className="text-sm text-gray-500">
            Phase 1: Project Foundation Complete
          </p>
          <div className="mt-4 space-y-2 text-left text-sm">
            <p className="flex items-center text-green-600">
              <span className="mr-2">✓</span> Backend API running
            </p>
            <p className="flex items-center text-green-600">
              <span className="mr-2">✓</span> Frontend loading
            </p>
            <p className="flex items-center text-green-600">
              <span className="mr-2">✓</span> Database connected
            </p>
          </div>
        </div>
        <p className="mt-6 text-xs text-gray-400">
          Ready for Phase 2: Authentication
        </p>
      </div>
    </div>
  )
}
