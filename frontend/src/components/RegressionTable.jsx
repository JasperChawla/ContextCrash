function getLevel(rate) {
  if (rate > 0.5)  return { label: 'CRITICAL',  bg: 'rgba(248,113,113,0.15)', text: '#F87171' }
  if (rate > 0.25) return { label: 'WARNING',   bg: 'rgba(251,146,60,0.15)',  text: '#FB923C' }
  if (rate > 0.1)  return { label: 'ELEVATED',  bg: 'rgba(251,191,36,0.12)',  text: '#FBBF24' }
  return             { label: 'NOMINAL',   bg: 'rgba(52,211,153,0.12)',  text: '#34D399' }
}

const COLS = ['Category', 'Model', 'Failure Rate', 'Avg Score', 'Tests', 'Status', 'Example']

export default function RegressionTable({ cells }) {
  if (!cells || cells.length === 0) {
    return (
      <div style={{ fontSize: '12px', color: '#71717A', padding: '16px 0' }}>
        No failure data available.
      </div>
    )
  }

  const sorted = [...cells].sort((a, b) => b.failure_rate - a.failure_rate)

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #27272A' }}>
            {COLS.map(h => (
              <th
                key={h}
                style={{ textAlign: 'left', padding: '8px 12px', fontSize: '10px', fontWeight: 600, letterSpacing: '0.06em', color: '#71717A', textTransform: 'uppercase' }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((c, i) => {
            const level = getLevel(c.failure_rate)
            return (
              <tr
                key={i}
                style={{ borderBottom: '1px solid #27272A' }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)' }}
                onMouseLeave={e => { e.currentTarget.style.background = '' }}
              >
                <td style={{ padding: '8px 12px', color: '#E4E4E7', fontWeight: 500 }}>{c.category}</td>
                <td style={{ padding: '8px 12px', color: '#71717A' }}>
                  {c.model.split('/').pop()}
                </td>
                <td style={{ padding: '8px 12px', fontWeight: 700, color: level.text }}>
                  {(c.failure_rate * 100).toFixed(1)}%
                </td>
                <td style={{ padding: '8px 12px', color: '#A1A1AA', fontFamily: 'monospace' }}>
                  {c.score?.toFixed(3) ?? '—'}
                </td>
                <td style={{ padding: '8px 12px', color: '#71717A' }}>{c.test_count}</td>
                <td style={{ padding: '8px 12px' }}>
                  <span className="badge" style={{ background: level.bg, color: level.text }}>
                    {level.label}
                  </span>
                  {c.disputed && (
                    <span className="badge" style={{ background: 'rgba(251,191,36,0.12)', color: '#FBBF24', marginLeft: '4px' }}>
                      DISPUTED
                    </span>
                  )}
                </td>
                <td style={{ padding: '8px 12px', color: '#71717A', fontSize: '11px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.example_reason || '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
