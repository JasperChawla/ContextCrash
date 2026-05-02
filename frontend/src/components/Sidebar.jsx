export default function Sidebar({ runs, selectedRunId, onSelectRun }) {
  return (
    <aside
      style={{
        flexShrink: 0,
        width: '240px',
        display: 'flex',
        flexDirection: 'column',
        background: '#18181B',
        borderRight: '1px solid #27272A',
        overflowY: 'auto',
      }}
    >
      {/* Section header */}
      <div style={{ padding: '12px 12px 8px', borderBottom: '1px solid #27272A' }}>
        <span style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.07em', color: '#71717A', textTransform: 'uppercase' }}>
          Evaluation Runs
        </span>
      </div>

      {/* Run list */}
      <div style={{ flex: 1, padding: '8px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
        {runs.length === 0 && (
          <div style={{ fontSize: '11px', color: '#71717A', padding: '16px 8px', textAlign: 'center' }}>
            No runs yet
          </div>
        )}
        {runs.map(run => {
          const active = run.run_id === selectedRunId
          const score = run.overall_score
          const scoreColor =
            score === null ? '#71717A'
            : score >= 0.8 ? '#34D399'
            : score >= 0.6 ? '#FBBF24'
            : '#F87171'
          const scoreText = score === null ? '—' : `${(score * 100).toFixed(0)}%`

          return (
            <button
              key={run.run_id}
              onClick={() => onSelectRun(run.run_id)}
              style={{
                width: '100%',
                textAlign: 'left',
                padding: '8px 10px',
                borderRadius: '4px',
                background: active ? '#09090B' : 'transparent',
                border: 'none',
                borderLeft: active ? '2px solid #3274D9' : '2px solid transparent',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                gap: '3px',
                transition: 'background 0.1s',
              }}
              onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'rgba(255,255,255,0.04)' }}
              onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                <span style={{
                  fontSize: '12px',
                  fontWeight: 500,
                  color: active ? '#3274D9' : '#E4E4E7',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  flex: 1,
                }}>
                  {run.suite_name}
                </span>
                <span style={{ fontSize: '10px', fontWeight: 700, color: scoreColor, flexShrink: 0 }}>
                  {scoreText}
                </span>
              </div>
              <div style={{ display: 'flex', gap: '8px', fontSize: '10px', color: '#71717A' }}>
                <span>{run.model_count}m · {run.test_count}t</span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {new Date(run.timestamp).toLocaleDateString()}
                </span>
              </div>
            </button>
          )
        })}
      </div>

      {/* Navigation */}
      <div style={{ padding: '12px', borderTop: '1px solid #27272A' }}>
        <div style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.07em', color: '#71717A', textTransform: 'uppercase', marginBottom: '6px' }}>
          Navigation
        </div>
        {['Dashboard', 'API Docs', 'Settings'].map(item => (
          <div
            key={item}
            style={{ fontSize: '12px', color: '#71717A', padding: '4px 8px', cursor: 'pointer', borderRadius: '4px' }}
            onMouseEnter={e => { e.currentTarget.style.color = '#E4E4E7' }}
            onMouseLeave={e => { e.currentTarget.style.color = '#71717A' }}
          >
            {item}
          </div>
        ))}
      </div>
    </aside>
  )
}
