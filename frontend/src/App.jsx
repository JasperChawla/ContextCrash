import { useEffect, useState } from 'react'
import {
  compareRunsById,
  fetchDegradation,
  fetchRunHeatmapV2,
  fetchRunSummaryFull,
  fetchRunsV2,
} from './api/client'
import CompareView from './components/CompareView'
import DegradationChart from './components/DegradationChart'
import HeatmapV2 from './components/HeatmapV2'
import MetricCards from './components/MetricCards'
import RegressionTable from './components/RegressionTable'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'

export default function App() {
  const [runs, setRuns] = useState([])
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [summary, setSummary] = useState(null)
  const [heatmap, setHeatmap] = useState([])
  const [degradation, setDegradation] = useState([])
  const [compareMode, setCompareMode] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Load runs list on mount
  useEffect(() => {
    fetchRunsV2()
      .then(data => {
        setRuns(data)
        if (data.length > 0) {
          setSelectedRunId(data[0].run_id)
        }
      })
      .catch(e => console.error('Failed to load runs:', e))
  }, [])

  // Load run data whenever selection changes
  useEffect(() => {
    if (!selectedRunId) return
    setLoading(true)
    setError(null)
    setSummary(null)
    setHeatmap([])
    setDegradation([])

    Promise.all([
      fetchRunSummaryFull(selectedRunId),
      fetchRunHeatmapV2(selectedRunId),
      fetchDegradation(selectedRunId),
    ])
      .then(([sum, hm, deg]) => {
        setSummary(sum)
        setHeatmap(hm)
        setDegradation(deg)
      })
      .catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }, [selectedRunId])

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#09090B', color: '#E4E4E7', fontFamily: "'Inter', system-ui, sans-serif", overflow: 'hidden' }}>
      <TopBar
        runs={runs}
        selectedRunId={selectedRunId}
        onRunChange={setSelectedRunId}
        compareMode={compareMode}
        onToggleCompare={() => setCompareMode(m => !m)}
      />
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <Sidebar
          runs={runs}
          selectedRunId={selectedRunId}
          onSelectRun={id => { setSelectedRunId(id); setCompareMode(false) }}
        />
        <main style={{ flex: 1, overflowY: 'auto' }}>
          {compareMode ? (
            <CompareView runs={runs} />
          ) : !selectedRunId ? (
            <EmptyState />
          ) : loading ? (
            <LoadingState />
          ) : error ? (
            <ErrorState message={error} />
          ) : (
            <Dashboard
              summary={summary}
              heatmap={heatmap}
              degradation={degradation}
              selectedRunId={selectedRunId}
            />
          )}
        </main>
      </div>
    </div>
  )
}

function Dashboard({ summary, heatmap, degradation, selectedRunId }) {
  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Run metadata strip */}
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', background: '#18181B', border: '1px solid #27272A', borderRadius: '4px', overflow: 'hidden' }}>
          {[
            { label: 'Suite', value: summary.suite_name },
            { label: 'Run ID', value: `${selectedRunId?.slice(0, 8)}…` },
            { label: 'Models', value: summary.models?.length ?? 0 },
            { label: 'Strongest', value: summary.strongest_model?.split('/').pop() ?? '—' },
            { label: 'Weakest', value: summary.weakest_model?.split('/').pop() ?? '—' },
          ].map(({ label, value }, i) => (
            <div
              key={label}
              style={{ padding: '12px 16px', borderLeft: i > 0 ? '1px solid #27272A' : 'none' }}
            >
              <div style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.07em', color: '#71717A', textTransform: 'uppercase', marginBottom: '4px' }}>
                {label}
              </div>
              <div style={{ fontSize: '12px', color: '#E4E4E7', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {value}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Metric cards */}
      <MetricCards summary={summary} />

      {/* Heatmap + Degradation */}
      <div style={{ display: 'grid', gridTemplateColumns: '7fr 5fr', gap: '16px' }}>
        <SectionCard title="Failure Heatmap" badge={`${heatmap.length} cells`}>
          <HeatmapV2 cells={heatmap} />
        </SectionCard>
        <SectionCard title="Degradation Curve" badge="Avg score vs depth">
          <DegradationChart data={degradation} />
        </SectionCard>
      </div>

      {/* Failure analysis table */}
      <SectionCard title="Failure Analysis" badge="Sorted by failure rate">
        <RegressionTable cells={heatmap} />
      </SectionCard>
    </div>
  )
}

function SectionCard({ title, badge, children }) {
  return (
    <div style={{ background: '#18181B', border: '1px solid #27272A', borderRadius: '4px' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #27272A', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.07em', color: '#71717A', textTransform: 'uppercase' }}>
          {title}
        </span>
        {badge && (
          <span style={{ fontSize: '10px', color: '#71717A' }}>{badge}</span>
        )}
      </div>
      <div style={{ padding: '16px' }}>
        {children}
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '16px', textAlign: 'center', padding: '48px' }}>
      <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: '#18181B', border: '1px solid #27272A', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#71717A" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      </div>
      <div>
        <h2 style={{ fontSize: '14px', fontWeight: 600, color: '#E4E4E7', margin: '0 0 6px' }}>No run selected</h2>
        <p style={{ fontSize: '12px', color: '#71717A', maxWidth: '320px' }}>
          Select a run from the sidebar, or run a benchmark suite with{' '}
          <code style={{ color: '#3274D9', fontFamily: 'monospace' }}>contextcrash run examples/suite.yaml</code>
        </p>
      </div>
    </div>
  )
}

function LoadingState() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '8px' }}>
      <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#3274D9', animation: 'pulse 1.2s ease-in-out infinite' }} />
      <span style={{ fontSize: '12px', color: '#71717A' }}>Loading run data…</span>
    </div>
  )
}

function ErrorState({ message }) {
  return (
    <div style={{ margin: '24px', fontSize: '12px', color: '#F87171', background: 'rgba(248,65,65,0.08)', border: '1px solid rgba(248,65,65,0.25)', borderRadius: '4px', padding: '12px 16px' }}>
      {message}
    </div>
  )
}
