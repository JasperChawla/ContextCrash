import * as d3 from 'd3'
import { useMemo, useState } from 'react'

const CATEGORIES = [
  'instruction_loss',
  'retrieval_overshadowing',
  'position_bias',
  'answer_truncation',
  'multi_turn_memory_decay',
  'contradiction_long_context',
  'citation_drift',
  'hallucination_overload',
]

const CAT_LABELS = {
  instruction_loss: 'Instruction\nLoss',
  retrieval_overshadowing: 'Retrieval\nOvershadowing',
  position_bias: 'Position\nBias',
  answer_truncation: 'Answer\nTruncation',
  multi_turn_memory_decay: 'Memory\nDecay',
  contradiction_long_context: 'Contradiction',
  citation_drift: 'Citation\nDrift',
  hallucination_overload: 'Hallucination',
}

// Color scale: dark green (pass) → bright red (fail)
// Using d3 diverging scale makes the 50% threshold visually obvious
const colorScale = d3.scaleSequential()
  .domain([0, 1])
  .interpolator(d3.interpolateRgb('#22c55e', '#ef4444'))

const CELL_W = 110
const CELL_H = 60
const MARGIN = { top: 80, left: 160, right: 40, bottom: 20 }

export default function Heatmap({ cells }) {
  const [tooltip, setTooltip] = useState(null)

  const models = useMemo(
    () => [...new Set(cells.map((c) => c.model))].sort(),
    [cells]
  )

  if (!cells || cells.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-500">
        No data available for this run.
      </div>
    )
  }

  const svgW = MARGIN.left + CATEGORIES.length * CELL_W + MARGIN.right
  const svgH = MARGIN.top + models.length * CELL_H + MARGIN.bottom

  // Build a lookup for O(1) cell access
  const lookup = {}
  for (const c of cells) {
    lookup[`${c.model}::${c.category}`] = c
  }

  return (
    <div className="relative overflow-x-auto">
      <svg width={svgW} height={svgH} className="select-none">
        {/* Column headers */}
        {CATEGORIES.map((cat, ci) => {
          const x = MARGIN.left + ci * CELL_W + CELL_W / 2
          const lines = (CAT_LABELS[cat] || cat).split('\n')
          return (
            <g key={cat} transform={`translate(${x}, ${MARGIN.top - 10})`}>
              {lines.map((line, li) => (
                <text
                  key={li}
                  textAnchor="middle"
                  dy={li === 0 ? `-${(lines.length - 1) * 12}px` : '14px'}
                  fontSize={11}
                  fill="#9ca3af"
                  fontFamily="monospace"
                >
                  {line}
                </text>
              ))}
            </g>
          )
        })}

        {/* Row labels */}
        {models.map((model, mi) => {
          const y = MARGIN.top + mi * CELL_H + CELL_H / 2
          return (
            <text
              key={model}
              x={MARGIN.left - 12}
              y={y}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize={12}
              fill="#e5e7eb"
              fontFamily="monospace"
            >
              {model.length > 20 ? model.slice(0, 18) + '…' : model}
            </text>
          )
        })}

        {/* Cells */}
        {models.map((model, mi) =>
          CATEGORIES.map((cat, ci) => {
            const cell = lookup[`${model}::${cat}`]
            const rate = cell ? cell.failure_rate : null
            const x = MARGIN.left + ci * CELL_W
            const y = MARGIN.top + mi * CELL_H
            const fill = rate !== null ? colorScale(rate) : '#1f2937'

            return (
              <g
                key={`${model}-${cat}`}
                className="heatmap-cell"
                onMouseEnter={(e) =>
                  setTooltip({
                    x: e.clientX,
                    y: e.clientY,
                    model,
                    cat,
                    cell,
                  })
                }
                onMouseLeave={() => setTooltip(null)}
              >
                <rect
                  x={x + 2}
                  y={y + 2}
                  width={CELL_W - 4}
                  height={CELL_H - 4}
                  rx={6}
                  fill={fill}
                  opacity={0.9}
                />
                <text
                  x={x + CELL_W / 2}
                  y={y + CELL_H / 2}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize={14}
                  fontWeight="bold"
                  fill={rate !== null && rate > 0.4 ? '#fff' : '#111'}
                  fontFamily="monospace"
                >
                  {rate !== null ? `${(rate * 100).toFixed(0)}%` : '—'}
                </text>
              </g>
            )
          })
        )}

        {/* Gradient legend bar */}
        <defs>
          <linearGradient id="legend-grad" x1="0" x2="1">
            <stop offset="0%" stopColor="#22c55e" />
            <stop offset="50%" stopColor="#facc15" />
            <stop offset="100%" stopColor="#ef4444" />
          </linearGradient>
        </defs>
        <rect
          x={MARGIN.left}
          y={svgH - 14}
          width={CATEGORIES.length * CELL_W}
          height={8}
          rx={4}
          fill="url(#legend-grad)"
          opacity={0.7}
        />
        <text x={MARGIN.left} y={svgH - 16} fontSize={10} fill="#6b7280" fontFamily="monospace">0%</text>
        <text
          x={MARGIN.left + CATEGORIES.length * CELL_W}
          y={svgH - 16}
          fontSize={10}
          fill="#6b7280"
          textAnchor="end"
          fontFamily="monospace"
        >
          100%
        </text>
      </svg>

      {/* Tooltip rendered outside SVG for correct stacking */}
      {tooltip && tooltip.cell && (
        <div
          className="tooltip"
          style={{ left: tooltip.x + 12, top: tooltip.y - 60, position: 'fixed' }}
        >
          <div className="font-bold text-white">{tooltip.model}</div>
          <div className="text-gray-400">{tooltip.cat.replace(/_/g, ' ')}</div>
          <div className="mt-1">
            <span className="text-red-400">Failure rate:</span>{' '}
            <span className="text-white">{(tooltip.cell.failure_rate * 100).toFixed(1)}%</span>
          </div>
          <div>
            <span className="text-gray-400">Tests:</span>{' '}
            <span className="text-white">{tooltip.cell.total}</span>
          </div>
          <div>
            <span className="text-gray-400">Avg score:</span>{' '}
            <span className="text-white">{tooltip.cell.avg_score.toFixed(2)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
