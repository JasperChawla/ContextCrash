import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({ baseURL: BASE, timeout: 120_000 })

// Legacy endpoints (kept for backward compatibility)
export async function fetchRuns() {
  const { data } = await api.get('/results/runs')
  return data
}
export async function fetchSummaries(runId) {
  const { data } = await api.get(`/results/runs/${runId}/summaries`)
  return data
}
export async function fetchHeatmap(runId) {
  const { data } = await api.get(`/results/runs/${runId}/heatmap`)
  return data
}
export async function fetchRawResults(runId) {
  const { data } = await api.get(`/results/runs/${runId}/raw`)
  return data
}
export async function startRun(suiteYaml, modelOverrides) {
  const { data } = await api.post('/runs/', {
    suite_yaml: suiteYaml,
    model_overrides: modelOverrides || null,
  })
  return data
}
export async function compareRuns(baselineYaml, candidateYaml) {
  const { data } = await api.post('/runs/compare', {
    baseline_yaml: baselineYaml,
    candidate_yaml: candidateYaml,
  })
  return data
}

// Phase 3A endpoints
export async function fetchRunsV2() {
  const { data } = await api.get('/api/runs')
  return data
}
export async function fetchRunHeatmapV2(runId) {
  const { data } = await api.get(`/api/runs/${runId}/heatmap`)
  return data
}
export async function fetchDegradation(runId) {
  const { data } = await api.get(`/api/runs/${runId}/degradation`)
  return data
}
export async function fetchRunSummaryFull(runId) {
  const { data } = await api.get(`/api/runs/${runId}/summary`)
  return data
}
export async function compareRunsById(baselineId, candidateId) {
  const { data } = await api.get('/api/runs/compare', {
    params: { baseline: baselineId, candidate: candidateId },
  })
  return data
}
