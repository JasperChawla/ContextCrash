import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

const LINE_COLORS = ['#3274D9', '#34D399', '#FBBF24', '#F87171', '#A78BFA', '#38BDF8', '#FB923C']

export default function DegradationChart({ data }) {
  const svgRef = useRef(null)

  useEffect(() => {
    if (!svgRef.current) return
    const el = svgRef.current
    d3.select(el).selectAll('*').remove()

    if (!data || data.length === 0) return

    const margin = { top: 16, right: 90, bottom: 36, left: 44 }
    const totalW = el.clientWidth || 380
    const totalH = 200
    const W = totalW - margin.left - margin.right
    const H = totalH - margin.top - margin.bottom

    // Group by model; average score across all categories per depth level
    const byModel = d3.group(data, d => d.model)
    const series = Array.from(byModel, ([model, rows]) => {
      const byDepth = d3.rollup(rows, v => d3.mean(v, d => d.avg_score), d => d.depth_level)
      const points = Array.from(byDepth, ([x, y]) => ({ x, y })).sort((a, b) => a.x - b.x)
      return { model, points }
    })

    const allX = data.map(d => d.depth_level)
    const xDomain = d3.extent(allX)

    const x = d3.scaleLinear().domain(xDomain).range([0, W]).nice()
    const y = d3.scaleLinear().domain([0, 1]).range([H, 0])

    const svg = d3.select(el)
      .attr('viewBox', `0 0 ${totalW} ${totalH}`)
      .attr('width', '100%')
      .attr('height', totalH)

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

    // Grid
    g.append('g')
      .call(d3.axisLeft(y).tickSize(-W).tickFormat('').ticks(4))
      .call(g => {
        g.select('.domain').remove()
        g.selectAll('line').attr('stroke', '#27272A').attr('stroke-dasharray', '2,3')
      })

    // X axis
    g.append('g')
      .attr('transform', `translate(0,${H})`)
      .call(d3.axisBottom(x).ticks(5))
      .call(g => {
        g.select('.domain').attr('stroke', '#27272A')
        g.selectAll('text').attr('fill', '#71717A').attr('font-size', '10px').attr('font-family', 'Inter')
        g.selectAll('.tick line').attr('stroke', '#27272A')
      })

    // X axis label
    g.append('text')
      .attr('x', W / 2).attr('y', H + 30)
      .attr('text-anchor', 'middle')
      .attr('fill', '#71717A').attr('font-size', '10px').attr('font-family', 'Inter')
      .text('Context Depth Level')

    // Y axis
    g.append('g')
      .call(d3.axisLeft(y).ticks(4).tickFormat(d => `${(d * 100).toFixed(0)}%`))
      .call(g => {
        g.select('.domain').attr('stroke', '#27272A')
        g.selectAll('text').attr('fill', '#71717A').attr('font-size', '10px').attr('font-family', 'Inter')
        g.selectAll('.tick line').attr('stroke', '#27272A')
      })

    // Lines + dots
    const line = d3.line()
      .x(d => x(d.x))
      .y(d => y(d.y))
      .curve(d3.curveMonotoneX)

    series.forEach(({ model, points }, i) => {
      const color = LINE_COLORS[i % LINE_COLORS.length]

      g.append('path')
        .datum(points)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 1.5)
        .attr('d', line)

      g.selectAll(null)
        .data(points)
        .join('circle')
        .attr('cx', d => x(d.x))
        .attr('cy', d => y(d.y))
        .attr('r', 3)
        .attr('fill', color)
        .attr('stroke', '#09090B')
        .attr('stroke-width', 1)
    })

    // Legend (right side)
    const legendG = svg.append('g').attr('transform', `translate(${totalW - margin.right + 8}, ${margin.top})`)
    series.forEach(({ model }, i) => {
      const color = LINE_COLORS[i % LINE_COLORS.length]
      const shortName = model.split('/').pop().slice(0, 14)
      legendG.append('line')
        .attr('x1', 0).attr('x2', 14)
        .attr('y1', i * 16 + 7).attr('y2', i * 16 + 7)
        .attr('stroke', color).attr('stroke-width', 1.5)
      legendG.append('circle')
        .attr('cx', 7).attr('cy', i * 16 + 7).attr('r', 3)
        .attr('fill', color)
      legendG.append('text')
        .attr('x', 18).attr('y', i * 16 + 11)
        .attr('fill', '#A1A1AA').attr('font-size', '10px').attr('font-family', 'Inter')
        .text(shortName)
    })
  }, [data])

  if (!data || data.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px', fontSize: '12px', color: '#71717A' }}>
        No degradation data — depth-level tests not configured for this suite
      </div>
    )
  }

  return <svg ref={svgRef} style={{ width: '100%', display: 'block' }} />
}
