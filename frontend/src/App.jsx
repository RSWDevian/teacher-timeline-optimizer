import { useEffect, useMemo, useRef, useState } from 'react'
import { api, pollJob } from './api'
import EntityEditor from './components/EntityEditor.jsx'
import PreferencesPanel from './components/PreferencesPanel.jsx'
import TimetableGrid from './components/TimetableGrid.jsx'
import SchedulesPanel from './components/SchedulesPanel.jsx'

const DEMO = {
  name: 'Demo — Grade 9',
  description: 'Sample data to try the optimizer',
  teachers: [
    { id: 't1', name: 'Smith', subject: ['Math'], available_days: ['Mon', 'Tue', 'Wed'],
      max_hours_per_week: 15, unavailable_slots: ['Mon-1'] },
    { id: 't2', name: 'Jones', subject: ['Chemistry'], available_days: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
      max_hours_per_week: 10, unavailable_slots: [] },
  ],
  rooms: [
    { id: 'r1', capacity: 30, is_lab: false },
    { id: 'r2', capacity: 32, is_lab: true },
  ],
  class_groups: [{ id: 'g1', name: 'Grade 9-A', size: 25 }],
  courses: [
    { id: 'c1', subject: 'Math', required_hours: 3, requires_lab: false,
      allowed_teachers: ['t1'], class_group_id: 'g1', max_per_day: 2 },
    { id: 'c2', subject: 'Chemistry', required_hours: 2, requires_lab: true,
      allowed_teachers: ['t2'], class_group_id: 'g1', max_per_day: null },
  ],
  preferences: { balance_weight: 1, gap_weight: 10, spread_weight: 3, time_limit_seconds: 30 },
}

const EMPTY_PREFERENCES = { balance_weight: 1, gap_weight: 10, spread_weight: 3, time_limit_seconds: 30 }

const blankDraft = () => ({
  name: 'New scenario',
  description: '',
  teachers: [],
  rooms: [],
  class_groups: [],
  courses: [],
  preferences: { ...EMPTY_PREFERENCES },
})

const TEACHER_FIELDS = [
  { key: 'id', label: 'ID', placeholder: 't1' },
  { key: 'name', label: 'Name', placeholder: 'Smith' },
  { key: 'subject', label: 'Subjects', type: 'tags', placeholder: 'Math, Physics' },
  { key: 'available_days', label: 'Available days (empty = all)', type: 'days' },
  { key: 'max_hours_per_week', label: 'Max hours / week', type: 'number', default: 10 },
  { key: 'unavailable_slots', label: 'Blocked slots', type: 'tags', placeholder: 'Mon-1, Wed-3' },
]

const ROOM_FIELDS = [
  { key: 'id', label: 'ID', placeholder: 'r1' },
  { key: 'capacity', label: 'Capacity', type: 'number', default: 30 },
  { key: 'is_lab', label: 'Is a lab', type: 'checkbox' },
]

const GROUP_FIELDS = [
  { key: 'id', label: 'ID', placeholder: 'g1' },
  { key: 'name', label: 'Name', placeholder: 'Grade 9-A' },
  { key: 'size', label: 'Students', type: 'number', default: 25 },
]

const COURSE_FIELDS = [
  { key: 'id', label: 'ID', placeholder: 'c1' },
  { key: 'subject', label: 'Subject', placeholder: 'Math' },
  { key: 'required_hours', label: 'Required hours / week', type: 'number', default: 2 },
  { key: 'requires_lab', label: 'Needs a lab', type: 'checkbox' },
  { key: 'allowed_teachers', label: 'Allowed teachers', type: 'teachers' },
  { key: 'class_group_id', label: 'Class group', type: 'select', none: true, options: [] },
  { key: 'max_per_day', label: 'Max sessions / day (blank = none)', type: 'number', nullable: true },
]

export default function App() {
  const [scenarios, setScenarios] = useState([])
  const [currentId, setCurrentId] = useState(null)
  const [draft, setDraft] = useState(blankDraft())
  const [savedSnapshot, setSavedSnapshot] = useState(JSON.stringify(blankDraft()))
  const [result, setResult] = useState(null)
  const [viewedSchedule, setViewedSchedule] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(null) // 'optimize' | 'save'
  const [refreshKey, setRefreshKey] = useState(0)
  const gridRef = useRef(null)

  const dirty = useMemo(() => JSON.stringify(draft) !== savedSnapshot, [draft, savedSnapshot])
  const courseFields = useMemo(() => [
    ...COURSE_FIELDS.slice(0, 5),
    { ...COURSE_FIELDS[5], options: draft.class_groups.map((g) => ({ value: g.id, label: g.name || g.id })) },
    COURSE_FIELDS[6],
  ], [draft.class_groups])

  useEffect(() => {
    api.listScenarios().then(setScenarios).catch((e) => setError(e.message))
  }, [refreshKey])

  const loadScenario = async (id) => {
    setError('')
    try {
      const full = await api.getScenario(id)
      applyScenario(full, id)
      setResult(null)
      setViewedSchedule(null)
    } catch (e) { setError(e.message) }
  }

  const applyScenario = (full, id = full.id) => {
    const d = {
      name: full.name,
      description: full.description || '',
      teachers: full.teachers || [],
      rooms: full.rooms || [],
      class_groups: full.class_groups || [],
      courses: full.courses || [],
      preferences: { ...EMPTY_PREFERENCES, ...(full.preferences || {}) },
    }
    setDraft(d)
    setSavedSnapshot(JSON.stringify(d))
    setCurrentId(id)
  }

  const newScenario = () => {
    const d = blankDraft()
    setDraft(d)
    setSavedSnapshot(JSON.stringify(d))
    setCurrentId(null)
    setResult(null)
    setViewedSchedule(null)
  }

  const loadDemo = () => {
    setDraft({ ...DEMO, preferences: { ...DEMO.preferences } })
    setCurrentId(null)
    setError('')
  }

  const save = async () => {
    setBusy('save')
    setError('')
    try {
      const payload = {
        name: draft.name || 'Untitled',
        description: draft.description,
        teachers: draft.teachers,
        rooms: draft.rooms,
        class_groups: draft.class_groups,
        courses: draft.courses,
        preferences: draft.preferences,
      }
      const saved = currentId
        ? await api.updateScenario(currentId, payload)
        : await api.createScenario(payload)
      applyScenario(saved, saved.id)
      setRefreshKey((k) => k + 1)
      return saved.id
    } catch (e) {
      setError(e.message)
      return null
    } finally { setBusy(null) }
  }

  const removeScenario = async (id) => {
    setError('')
    try {
      await api.deleteScenario(id)
      if (id === currentId) newScenario()
      setRefreshKey((k) => k + 1)
    } catch (e) { setError(e.message) }
  }

  const optimize = async () => {
    setBusy('optimize')
    setError('')
    setResult(null)
    try {
      let sid = currentId
      if (dirty || !sid) {
        sid = await save()
        if (!sid) return
      }
      const { job_id } = await api.optimize(sid)
      const job = await pollJob(job_id, {
        timeoutMs: (draft.preferences.time_limit_seconds + 20) * 1000,
      })
      if (job.result.status !== 'success') {
        setError(job.result.message || 'No feasible schedule found.')
      } else {
        setResult(job.result)
        setViewedSchedule(job.result.schedule)
      }
      setRefreshKey((k) => k + 1)
      gridRef.current?.scrollIntoView({ behavior: 'smooth' })
    } catch (e) {
      setError(e.message)
    } finally { setBusy(null) }
  }

  const setEntities = (key) => (items) => setDraft({ ...draft, [key]: items })

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3">
          <h1 className="text-lg font-bold">Teacher Timetable Optimizer</h1>
          <span className="text-xs text-slate-400">React · FastAPI · CP-SAT</span>
          <div className="ml-auto flex items-center gap-2">
            {dirty && <span className="text-xs font-medium text-amber-600">unsaved changes</span>}
            <button onClick={save} disabled={busy === 'save'}
                    className="rounded bg-slate-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-900 disabled:opacity-50">
              {busy === 'save' ? 'Saving…' : currentId ? 'Save scenario' : 'Create scenario'}
            </button>
            <button onClick={optimize} disabled={busy === 'optimize'}
                    className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
              {busy === 'optimize' ? 'Optimizing…' : 'Optimize schedule'}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-4">
        {error && (
          <div className="mb-4 rounded border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}

        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
          <select value={currentId ?? ''} onChange={(e) => e.target.value ? loadScenario(Number(e.target.value)) : newScenario()}
                  className="rounded border border-slate-300 px-2 py-1.5 text-sm">
            <option value="">— select scenario —</option>
            {scenarios.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <button onClick={newScenario} className="rounded border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50">New</button>
          <button onClick={loadDemo} className="rounded border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50">Load demo data</button>
          <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                 placeholder="Scenario name"
                 className="ml-auto w-56 rounded border border-slate-300 px-2 py-1.5 text-sm" />
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <div className="space-y-4">
            <EntityEditor title="Teachers" fields={TEACHER_FIELDS} items={draft.teachers}
                          onChange={setEntities('teachers')} />
            <EntityEditor title="Rooms" fields={ROOM_FIELDS} items={draft.rooms}
                          onChange={setEntities('rooms')} />
            <EntityEditor title="Class groups" fields={GROUP_FIELDS} items={draft.class_groups}
                          onChange={setEntities('class_groups')} />
            <EntityEditor title="Courses" fields={courseFields} items={draft.courses}
                          onChange={setEntities('courses')}
                          options={{ teachers: draft.teachers.map((t) => t.id) }} />
            <PreferencesPanel preferences={draft.preferences}
                              onChange={(p) => setDraft({ ...draft, preferences: p })} />
          </div>

          <div className="space-y-4">
            <div ref={gridRef}>
              <TimetableGrid entries={viewedSchedule || []}
                             teachers={draft.teachers} rooms={draft.rooms}
                             groups={draft.class_groups} courses={draft.courses} />
            </div>
            {result && (
              <section className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-sm shadow-sm">
                <div className="font-semibold text-emerald-700">Optimization succeeded</div>
                <div className="mt-1 text-xs text-emerald-800">
                  {result.stats?.status} · solve time {result.stats?.solve_time_seconds}s
                  {result.objective_value != null && <> · objective {result.objective_value}</>}
                  {result.schedule_id && <> · saved as schedule #{result.schedule_id}</>}
                </div>
              </section>
            )}
            <SchedulesPanel scenarioId={currentId} refreshKey={refreshKey}
                            onView={(full) => setViewedSchedule(full.schedule)} />
            <section className="rounded-lg border border-slate-200 bg-white p-4 text-xs shadow-sm">
              <h3 className="mb-2 text-sm font-semibold text-slate-800">Quick reference</h3>
              <ul className="list-disc space-y-1 pl-4 text-slate-500">
                <li>Teachers must list the course subject to be eligible.</li>
                <li>Lab courses only fit lab rooms with capacity ≥ class size.</li>
                <li>Blocked slots use <code>Day-Period</code> format, e.g. <code>Mon-1</code>.</li>
                <li>Saving a scenario stores it in the backend; optimization runs asynchronously and auto-saves results.</li>
              </ul>
            </section>
          </div>
        </div>
      </main>
    </div>
  )
}
