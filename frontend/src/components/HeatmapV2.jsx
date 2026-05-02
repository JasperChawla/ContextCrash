import { useState } from 'react'

const LEVELS = [
  { label: 'NOMINAL',  threshold: 0.10, bg: 'rgba(52,211,153,0.15)',  text: '#34D399', border: 'rgba(52,211,153,0.25)' },
  { label: 'ELEVATED', threshold: 0.25, bg: 'rgba(251,191,36,0.15)',  text: '#FBBF24', border: 'rgba(251,191,36,0.25)' },
  { label: 'WARNING',  threshold: 0.50, bg: 'rgba(251,146,60,0.15)',  text: '#FB923C', border: 'rgba(251,146,60,0.25)' },
  { label: 'CRITICAL', threshold: 1.01, bg: 'rgba(248,113,113,0.15)', text: '#F87171', border: 'rgba(248,113,113,0.25)' },
]

function getLevel(rate) {
  return LEVELS.find(l => rate <= l.threshold) ?? LEVELS[3]
}

export default function HeatmapV2({ cells }) {
  const [tooltip, setTooltip] = useState(null)

  if (!cells || cells.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '120px', fontSize: '12px', color: '#71717A' }}>
        No heatmap data for this run
      </div>
    )
  }

  const models = [...new Set(cells.map(c => c.model))].sort()
  const categories = [...new Set(cells.map(c => c.category))].sort()
  const lookup = new Map(cells.map(c => [`${c.model}|${c.category}`, c]))

  return (
    <div>
      {/* Legend */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '12px' }}>
        {LEVELS.map(l => (
          <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '2px', background: l.text }} />
            <span style={{ fontSize: '10px', fontWeight: 600, color: '#71717A', letterSpacing: '0.05em' }}>
              {l.label}
            </span>
          </div>
        ))}
      </div>

      {/* Grid */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', fontSize: '10px', color: '#71717A', fontWeight: 500, paddingBottom: '8px', paddingRight: '16px', width: '140px' }}>
                Category
              </th>
              {models.map(m => (
                <th
                  key={m}
                  style={{ fontSize: '10px', color: '#71717A', fontWeight: 500, paddingBottom: '8px', paddingLeft: '4px', paddingRight: '4px', textAlign: 'center', minWidth: '88px' }}
                  title={m}
                >
                  <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '80px' }}>
                    {m.split('/').pop()}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {categories.map(cat => (
              <tr key={cat}>
                <td
                  style={{ fontSize: '11px', color: '#A1A1AA', paddingTop: '4px', paddingBottom: '4px', paddingRight: '16px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '140px' }}
                  title={cat}
                >
                  {cat}
                </td>
                {models.map(model => {
                  const cell = lookup.get(`${model}|${cat}`)
                  if (!cell) {
                    return (
                      <td key={model} style={{ padding: '4px' }}>
                        <div style={{ height: '36px', borderRadius: '4px', background: '#18181B', border: '1px solid #27272A', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', color: '#3f3f46' }}>
                          —
                        </div>
                      </td>
                    )
                  }
                  const level = getLevel(cell.failure_rate)
                  return (
                    <td key={model} style={{ padding: '4px' }}>
                      <div
                        style={{ height: '36px', borderRadius: '4px', background: level.bg, border: `1px solid ${level.border}`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', cursor: 'default', transition: 'filter 0.12s' }}
                        onMouseEnter={e => {
                          e.currentTarget.style.filter = 'brightness(1.3)'
                          setTooltip({ cell, x: e.clientX + 14, y: e.clientY + 14 })
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.filter = ''
                          setTooltip(null)
                        }}
                        onMouseMove={e => setTooltip(t => t ? { ...t, x: e.clientX + 14, y: e.clientY + 14 } : null)}
                      >
                        <span style={{ fontSize: '12px', fontWeight: 700, color: level.text, lineHeight: 1 }}>
                          {(cell.failure_rate * 100).toFixed(0)}%
                        </span>
                        <span style={{ fontSize: '9px', color: level.text, opacity: 0.65, lineHeight: 1, marginTop: '2px' }}>
                          {cell.test_count}t
                        </span>
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div className="cc-tooltip" style={{ left: tooltip.x, top: tooltip.y }}>
          <div style={{ fontWeight: 600, marginBottom: '4px', color: '#E4E4E7' }}>{tooltip.cell.category}</div>
          <div style={{ color: '#71717A', marginBottom: '8px' }}>{tooltip.cell.model}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            <div>Failure rate: <span style={{ color: '#fff', fontWeight: 600 }}>{(tooltip.cell.failure_rate * 100).toFixed(1)}%</span></div>
            <div>Avg score: <span style={{ color: '#fff', fontWeight: 600 }}>{tooltip.cell.score?.toFixed(3) ?? '—'}</span></div>
            <div>Tests: <span style={{ color: '#fff', fontWeight: 600 }}>{tooltip.cell.test_count}</span></div>
            {tooltip.cell.disputed && (
              <div style={{ color: '#FBBF24', marginTop: '4px' }}>⚠ Contains disputed results</div>
            )}
            {tooltip.cell.example_reason && (
              <div style={{ marginTop: '6px', color: '#A1A1AA', fontSize: '10px', borderTop: '1px solid #27272A', paddingTop: '6px' }}>
                {tooltip.cell.example_reason.slice(0, 100)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
