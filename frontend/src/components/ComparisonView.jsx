import * as d3 from 'd3'
import { useMemo } from 'react'

// Delta bar chart: positive = regression (red), negative = improvement (green)
const barScale = d3.scaleLinear().domain([-1, 1]).range([0, 400])
const MIDPOINT = barScale(0)

export default function ComparisonView({ comparisons }) {
  if (!comparisons || comparisons.length === 0) {
    return (
      <div className="text-gray-500 text-center py-12">
        No comparison data. Run a compare to see regression deltas.
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {comparisons.map((comp) => (
        <ModelComparison key={comp.model} comp={comp} />
      ))}
    </div>
  )
}

function ModelComparison({ comp }) {
  const overallColor =
    comp.overall_delta > 0.05
      ? 'text-red-400'
      : comp.overall_delta < -0.05
      ? 'text-green-400'
      : 'text-gray-400'

  return (
    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-cyan-400 font-mono">{comp.model}</h3>
        <div className="text-sm text-gray-400">
          <span className="text-gray-500">baseline</span>{' '}
          <span className="text-yellow-400">{(comp.baseline_failure_rate * 100).toFixed(1)}%</span>
          <span className="text-gray-600 mx-2">→</span>
          <span className="text-gray-500">candidate</span>{' '}
          <span className="text-yellow-400">{(comp.candidate_failure_rate * 100).toFixed(1)}%</span>
          <span className="ml-4 font-bold">
            overall delta:{' '}
            <span className={overallColor}>
              {comp.overall_delta >= 0 ? '+' : ''}{(comp.overall_delta * 100).toFixed(1)}%
            </span>
          </span>
        </div>
      </div>

      <div className="space-y-2">
        {comp.category_deltas
          .slice()
          .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
          .map((cat) => (
            <DeltaBar key={cat.category} cat={cat} />
          ))}
      </div>
    </div>
  )
}

function DeltaBar({ cat }) {
  const isRegression = cat.delta > 0
  const isImprovement = cat.delta < 0
  const magnitude = Math.abs(cat.delta)

  const barWidth = Math.min(magnitude * 400, 200) // cap at 200px visual
  const color = isRegression ? '#ef4444' : isImprovement ? '#22c55e' : '#6b7280'

  return (
    <div className="flex items-center gap-3 py-1">
      <div className="w-48 text-xs text-gray-400 text-right font-mono truncate">
        {cat.category.replace(/_/g, ' ')}
      </div>

      <div className="flex items-center gap-1 w-64 relative">
        {/* Zero line */}
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-700" />

        {isImprovement ? (
          <div
            className="absolute h-5 rounded"
            style={{
              right: '50%',
              width: barWidth,
              backgroundColor: color,
              opacity: 0.8,
            }}
          />
        ) : (
          <div
            className="absolute h-5 rounded"
            style={{
              left: '50%',
              width: barWidth,
              backgroundColor: color,
              opacity: 0.8,
            }}
          />
        )}
      </div>

      <div className="text-xs font-mono w-16 text-right" style={{ color }}>
        {cat.delta >= 0 ? '+' : ''}{(cat.delta * 100).toFixed(1)}%
      </div>

      <div className="text-xs text-gray-600 font-mono">
        {(cat.baseline_rate * 100).toFixed(0)}% → {(cat.candidate_rate * 100).toFixed(0)}%
      </div>
    </div>
  )
}
