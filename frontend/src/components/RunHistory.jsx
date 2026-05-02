import { useEffect, useState } from 'react'
import { fetchRuns, fetchSummaries } from '../api/client'

export default function RunHistory({ onSelectRun, selectedRunId }) {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchRuns()
      .then(setRuns)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-gray-500 text-sm">Loading runs...</div>
  if (error) return <div className="text-red-400 text-sm">Error: {error}</div>
  if (runs.length === 0) return <div className="text-gray-500 text-sm">No runs yet. Run a suite to get started.</div>

  return (
    <div className="space-y-1">
      {runs.map((run) => {
        const isSelected = run.run_id === selectedRunId
        const models = JSON.parse(run.models_json || '[]')
        const date = new Date(run.created_at).toLocaleString()

        return (
          <button
            key={run.run_id}
            onClick={() => onSelectRun(run.run_id)}
            className={`w-full text-left px-4 py-3 rounded-lg transition-colors ${
              isSelected
                ? 'bg-cyan-900/40 border border-cyan-700'
                : 'bg-gray-900 border border-gray-800 hover:border-gray-600'
            }`}
          >
            <div className="text-sm font-bold text-white font-mono truncate">
              {run.suite_name}
            </div>
            <div className="text-xs text-gray-500 mt-0.5 font-mono">
              {date} · {models.length} model{models.length !== 1 ? 's' : ''}
            </div>
            <div className="text-xs text-gray-600 mt-0.5 font-mono truncate">
              {run.run_id.slice(0, 8)}…
            </div>
          </button>
        )
      })}
    </div>
  )
}
