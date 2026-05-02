import { useState } from 'react'
import { compareRunsById } from '../api/client'

function statusStyle(status) {
  if (status === 'REGRESSION') return { bg: 'rgba(248,113,113,0.15)', text: '#F87171' }
  if (status === 'IMPROVED')   return { bg: 'rgba(52,211,153,0.12)',  text: '#34D399' }
  return                         { bg: 'rgba(113,113,122,0.15)',       text: '#71717A' }
}

const CARD_STYLE = {
  background: '#18181B',
  border: '1px solid #27272A',
  borderRadius: '4px',
  padding: '16px',
}

export default function CompareView({ runs }) {
  const [baselineId, setBaselineId] = useState('')
  const [candidateId, setCandidateId] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleCompare() {
    if (!baselineId || !candidateId) return
    setLoading(true)
    setError(null)
    setResults(null)
    try {
      const data = await compareRunsById(baselineId, candidateId)
      setResults(data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  const totalRegressions = results
    ? results.reduce((a, r) => a + r.category_deltas.filter(d => d.status === 'REGRESSION').length, 0)
    : 0
  const totalImprovements = results
    ? results.reduce((a, r) => a + r.category_deltas.filter(d => d.status === 'IMPROVED').length, 0)
    : 0
  const avgDelta = results && results.length > 0
    ? results.reduce((a, r) => a + r.overall_delta, 0) / results.length
    : null

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Breadcrumb + title */}
      <div>
        <div style={{ fontSize: '10px', color: '#71717A', marginBottom: '4px', letterSpacing: '0.03em' }}>
          Models › Compare Regression Analysis
        </div>
        <h1 style={{ fontSize: '24px', fontWeight: 700, letterSpacing: '-0.02em', color: '#fff', margin: 0 }}>
          LLM Performance Delta
        </h1>
      </div>

      {/* Run selectors */}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '12px', flexWrap: 'wrap' }}>
        {[
          { label: 'Baseline Run', value: baselineId, onChange: setBaselineId },
          { label: 'Candidate Run', value: candidateId, onChange: setCandidateId },
        ].map(({ label, value, onChange }) => (
          <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.07em', color: '#71717A', textTransform: 'uppercase' }}>
              {label}
            </label>
            <select
              value={value}
              onChange={e => onChange(e.target.value)}
              style={{
                fontSize: '12px',
                background: '#18181B',
                border: '1px solid #27272A',
                borderRadius: '4px',
                padding: '6px 10px',
                color: '#E4E4E7',
                minWidth: '240px',
                outline: 'none',
              }}
            >
              <option value="">— select run —</option>
              {runs.map(r => (
                <option key={r.run_id} value={r.run_id}>
                  {r.suite_name} · {new Date(r.timestamp).toLocaleDateString()}
                </option>
              ))}
            </select>
          </div>
        ))}
        <button
          onClick={handleCompare}
          disabled={!baselineId || !candidateId || loading}
          style={{
            padding: '6px 16px',
            fontSize: '12px',
            fontWeight: 600,
            borderRadius: '4px',
            background: !baselineId || !candidateId || loading ? '#1D4A9F' : '#3274D9',
            color: '#fff',
            border: 'none',
            cursor: !baselineId || !candidateId || loading ? 'not-allowed' : 'pointer',
            opacity: !baselineId || !candidateId || loading ? 0.6 : 1,
            transition: 'opacity 0.15s',
          }}
        >
          {loading ? 'Comparing…' : 'Run Comparison'}
        </button>
      </div>

      {error && (
        <div style={{ fontSize: '12px', color: '#F87171', background: 'rgba(248,65,65,0.08)', border: '1px solid rgba(248,65,65,0.3)', borderRadius: '4px', padding: '10px 14px' }}>
          {error}
        </div>
      )}

      {results && (
        <>
          {/* Summary metric cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
            {[
              {
                label: 'Regressions',
                value: totalRegressions,
                color: totalRegressions > 0 ? '#F87171' : '#34D399',
              },
              {
                label: 'Improvements',
                value: totalImprovements,
                color: totalImprovements > 0 ? '#34D399' : '#71717A',
              },
              {
                label: 'Avg Score Delta',
                value: avgDelta !== null
                  ? `${avgDelta > 0 ? '+' : ''}${(avgDelta * 100).toFixed(1)}%`
                  : '—',
                color: avgDelta > 0.01 ? '#F87171' : avgDelta < -0.01 ? '#34D399' : '#71717A',
              },
              {
                label: 'Models Compared',
                value: results.length,
                color: '#E4E4E7',
              },
            ].map(card => (
              <div key={card.label} style={CARD_STYLE}>
                <div style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.07em', color: '#71717A', textTransform: 'uppercase', marginBottom: '12px' }}>
                  {card.label}
                </div>
                <div style={{ fontSize: '28px', fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1, color: card.color }}>
                  {card.value}
                </div>
              </div>
            ))}
          </div>

          {/* Per-model comparison tables */}
          {results.map(r => {
            const os = statusStyle(r.overall_status)
            return (
              <div key={r.model} style={{ background: '#18181B', border: '1px solid #27272A', borderRadius: '4px' }}>
                {/* Model header */}
                <div style={{ padding: '12px 16px', borderBottom: '1px solid #27272A', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: '#fff' }}>{r.model}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px' }}>
                    <span style={{ color: '#71717A' }}>
                      Baseline: <span style={{ color: '#E4E4E7', fontWeight: 600 }}>{(r.baseline_failure_rate * 100).toFixed(1)}%</span>
                    </span>
                    <span style={{ color: '#71717A' }}>
                      Candidate: <span style={{ color: '#E4E4E7', fontWeight: 600 }}>{(r.candidate_failure_rate * 100).toFixed(1)}%</span>
                    </span>
                    <span style={{ color: '#71717A' }}>
                      Delta: <span style={{ color: r.overall_delta > 0.01 ? '#F87171' : r.overall_delta < -0.01 ? '#34D399' : '#71717A', fontWeight: 600 }}>
                        {r.overall_delta > 0 ? '+' : ''}{(r.overall_delta * 100).toFixed(1)}%
                      </span>
                    </span>
                    <span className="badge" style={{ background: os.bg, color: os.text }}>
                      {r.overall_status}
                    </span>
                  </div>
                </div>

                {/* Category deltas table */}
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #27272A' }}>
                        {['Category', 'Baseline', 'Candidate', 'Delta', 'Status'].map(h => (
                          <th key={h} style={{ textAlign: 'left', padding: '8px 16px', fontSize: '10px', fontWeight: 600, letterSpacing: '0.06em', color: '#71717A', textTransform: 'uppercase' }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {r.category_deltas.map(d => {
                        const st = statusStyle(d.status)
                        const deltaColor = d.delta > 0.01 ? '#F87171' : d.delta < -0.01 ? '#34D399' : '#71717A'
                        return (
                          <tr
                            key={d.category}
                            style={{ borderBottom: '1px solid #27272A' }}
                            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)' }}
                            onMouseLeave={e => { e.currentTarget.style.background = '' }}
                          >
                            <td style={{ padding: '8px 16px', color: '#E4E4E7', fontWeight: 500 }}>{d.category}</td>
                            <td style={{ padding: '8px 16px', color: '#A1A1AA' }}>{(d.baseline_rate * 100).toFixed(1)}%</td>
                            <td style={{ padding: '8px 16px', color: '#A1A1AA' }}>{(d.candidate_rate * 100).toFixed(1)}%</td>
                            <td style={{ padding: '8px 16px', fontWeight: 700, fontFamily: 'monospace', color: deltaColor }}>
                              {d.delta > 0 ? '+' : ''}{(d.delta * 100).toFixed(1)}%
                            </td>
                            <td style={{ padding: '8px 16px' }}>
                              <span className="badge" style={{ background: st.bg, color: st.text }}>{d.status}</span>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )
          })}
        </>
      )}
    </div>
  )
}
