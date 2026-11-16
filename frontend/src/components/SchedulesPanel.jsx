import { useEffect, useState } from 'react'
import { api, download, scheduleToCsv } from '../api'

export default function SchedulesPanel({ scenarioId, refreshKey, onView }) {
  const [schedules, setSchedules] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    if (!scenarioId) return
    api.listSchedules(scenarioId)
      .then(setSchedules)
      .catch((e) => setError(e.message))
  }, [scenarioId, refreshKey])

  if (!scenarioId) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-800">Saved schedules</h3>
        <p className="text-xs text-slate-400">Save a scenario first to store optimized schedules.</p>
      </section>
    )
  }

  const load = async (id) => {
    setError('')
    try {
      const full = await api.getSchedule(scenarioId, id)
      onView(full)
    } catch (e) { setError(e.message) }
  }

  const remove = async (id) => {
    setError('')
    try {
      await api.deleteSchedule(scenarioId, id)
      setSchedules((s) => s.filter((x) => x.id !== id))
    } catch (e) { setError(e.message) }
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold text-slate-800">Saved schedules</h3>
      {error && <p className="mb-2 text-xs text-rose-600">{error}</p>}
      {schedules.length === 0 && <p className="text-xs text-slate-400">No schedules saved yet.</p>}
      <ul className="space-y-1">
        {schedules.map((s) => (
          <li key={s.id} className="flex items-center justify-between rounded bg-slate-50 px-2 py-1.5 text-xs">
            <div className="min-w-0">
              <div className="truncate font-medium text-slate-700">{s.name}</div>
              <div className="text-[11px] text-slate-400">
                {s.objective_value != null ? `score: ${s.objective_value} · ` : ''}
                {s.created_at ? new Date(s.created_at).toLocaleString() : ''}
              </div>
            </div>
            <div className="flex shrink-0 gap-2">
              <button onClick={() => load(s.id)} className="text-indigo-600 hover:underline">View</button>
              <button onClick={() => download(`${s.name.replace(/[^\w-]+/g, '_')}.json`,
                                             JSON.stringify(s.schedule, null, 2))}
                      className="text-slate-600 hover:underline">JSON</button>
              <button onClick={() => download(`${s.name.replace(/[^\w-]+/g, '_')}.csv`,
                                             scheduleToCsv(s.schedule), 'text/csv')}
                      className="text-slate-600 hover:underline">CSV</button>
              <button onClick={() => remove(s.id)} className="text-rose-600 hover:underline">Delete</button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
