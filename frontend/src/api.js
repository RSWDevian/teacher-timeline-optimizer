const BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  // '/health' lives at the root; everything else is under '/api'
  const url = path.startsWith('/api') ? path : `/api${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch { /* keep statusText */ }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  health: () => fetch('/health').then((r) => r.json()),

  listScenarios: () => request('/scenarios'),
  getScenario: (id) => request(`/scenarios/${id}`),
  createScenario: (data) => request('/scenarios', { method: 'POST', body: JSON.stringify(data) }),
  updateScenario: (id, data) => request(`/scenarios/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteScenario: (id) => request(`/scenarios/${id}`, { method: 'DELETE' }),

  optimize: (id) => request(`/scenarios/${id}/optimize?async=true`),
  getJob: (jobId) => request(`/jobs/${jobId}`),

  listSchedules: (scenarioId) => request(`/scenarios/${scenarioId}/schedules`),
  getSchedule: (scenarioId, scheduleId) => request(`/scenarios/${scenarioId}/schedules/${scheduleId}`),
  deleteSchedule: (scenarioId, scheduleId) =>
    request(`/scenarios/${scenarioId}/schedules/${scheduleId}`, { method: 'DELETE' }),
}

export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
export const PERIODS = [1, 2, 3, 4]

export async function pollJob(jobId, { intervalMs = 300, timeoutMs = 60000 } = {}) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    const job = await api.getJob(jobId)
    if (job.status === 'done') return job
    if (job.status === 'failed') throw new Error(job.error || 'Optimization job failed')
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  throw new Error('Timed out waiting for optimization job')
}

export function download(filename, content, type = 'application/json') {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function scheduleToCsv(entries) {
  const header = 'course,teacher,room,class_group,day,period\n'
  const rows = entries
    .map((e) => [e.course, e.teacher, e.room, e.class_group ?? '', e.day, e.period].join(','))
    .join('\n')
  return header + rows
}
