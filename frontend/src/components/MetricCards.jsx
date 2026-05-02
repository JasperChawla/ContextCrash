export default function MetricCards({ summary }) {
  if (!summary) return null

  const models = summary.models || []
  const avgFailureRate =
    models.length > 0
      ? models.reduce((a, m) => a + m.failure_rate, 0) / models.length
      : null
  const reliability = avgFailureRate !== null ? 1 - avgFailureRate : null
  const totalTests = models.reduce((a, m) => a + m.total_tests, 0)
  const totalFailures = models.reduce((a, m) => a + m.failed_tests, 0)

  const reliabilityColor =
    reliability === null ? '#71717A'
    : reliability >= 0.8 ? '#34D399'
    : reliability >= 0.6 ? '#FBBF24'
    : '#F87171'

  const cards = [
    {
      label: 'Overall Reliability',
      value: reliability !== null ? `${(reliability * 100).toFixed(1)}%` : '—',
      sub: reliability !== null
        ? (reliability >= 0.8 ? '↑ Within target threshold' : '↓ Below target threshold')
        : 'No data',
      valueColor: reliabilityColor,
    },
    {
      label: 'Total Tests',
      value: totalTests.toLocaleString(),
      sub: `Suite: ${summary.suite_name}`,
      valueColor: '#E4E4E7',
    },
    {
      label: 'Models Tested',
      value: models.length,
      sub: summary.strongest_model ? `Best: ${summary.strongest_model.split('/').pop()}` : '—',
      valueColor: '#E4E4E7',
    },
    {
      label: 'Failures Found',
      value: totalFailures.toLocaleString(),
      sub: summary.weakest_model ? `Worst: ${summary.weakest_model.split('/').pop()}` : '—',
      valueColor: totalFailures > 0 ? '#F87171' : '#34D399',
    },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
      {cards.map(card => (
        <div
          key={card.label}
          style={{
            background: '#18181B',
            border: '1px solid #27272A',
            borderRadius: '4px',
            padding: '16px',
          }}
        >
          <div style={{
            fontSize: '10px',
            fontWeight: 600,
            letterSpacing: '0.07em',
            color: '#71717A',
            textTransform: 'uppercase',
            marginBottom: '12px',
          }}>
            {card.label}
          </div>
          <div style={{
            fontSize: '28px',
            fontWeight: 700,
            letterSpacing: '-0.02em',
            lineHeight: 1,
            color: card.valueColor,
            marginBottom: '8px',
          }}>
            {card.value}
          </div>
          <div style={{
            fontSize: '11px',
            color: '#71717A',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {card.sub}
          </div>
        </div>
      ))}
    </div>
  )
}
