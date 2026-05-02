export default function TopBar({ runs, selectedRunId, onRunChange, compareMode, onToggleCompare }) {
  return (
    <header
      style={{
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '48px',
        padding: '0 16px',
        background: '#09090B',
        borderBottom: '1px solid #27272A',
      }}
    >
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3274D9" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
        <span style={{ fontSize: '14px', fontWeight: 900, letterSpacing: '-0.02em', color: '#fff' }}>
          ContextCrash
        </span>
        <span style={{ fontSize: '11px', color: '#71717A', letterSpacing: '0.01em' }}>
          LLM Reliability Benchmarking
        </span>
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        {/* Run selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.07em', color: '#71717A', textTransform: 'uppercase' }}>
            Active Run
          </span>
          <select
            value={selectedRunId || ''}
            onChange={e => onRunChange(e.target.value || null)}
            style={{
              fontSize: '12px',
              background: '#18181B',
              border: '1px solid #27272A',
              borderRadius: '4px',
              padding: '4px 8px',
              color: '#E4E4E7',
              minWidth: '200px',
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

        {/* Compare mode toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.07em', color: '#71717A', textTransform: 'uppercase' }}>
            Compare
          </span>
          <button
            onClick={onToggleCompare}
            style={{
              position: 'relative',
              width: '32px',
              height: '16px',
              borderRadius: '8px',
              background: compareMode ? '#3274D9' : '#27272A',
              border: 'none',
              cursor: 'pointer',
              transition: 'background 0.2s',
              padding: 0,
            }}
            aria-label="Toggle compare mode"
          >
            <span
              style={{
                position: 'absolute',
                top: '2px',
                left: compareMode ? '16px' : '2px',
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: '#fff',
                transition: 'left 0.2s',
              }}
            />
          </button>
        </div>
      </div>
    </header>
  )
}
