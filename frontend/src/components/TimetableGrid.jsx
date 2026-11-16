import { useState } from 'react'
import { DAYS, PERIODS } from '../api'

const PALETTE = ['#bfdbfe', '#fde68a', '#bbf7d0', '#fecaca', '#e9d5ff',
  '#fed7aa', '#a7f3d0', '#ddd6fe', '#fbcfe8', '#d9f99d']

const MODES = [
  { value: 'all', label: 'Everything' },
  { value: 'class_group', label: 'By class group' },
  { value: 'teacher', label: 'By teacher' },
  { value: 'room', label: 'By room' },
  { value: 'course', label: 'By course' },
]

function colorFor(courseId) {
  let h = 0
  for (const ch of String(courseId)) h = (h * 31 + ch.charCodeAt(0)) % 997
  return PALETTE[h % PALETTE.length]
}

export default function TimetableGrid({ entries, teachers, rooms, groups, courses }) {
  const [mode, setMode] = useState('all')
  const [focus, setFocus] = useState('')

  const courseById = Object.fromEntries((courses || []).map((c) => [c.id, c]))
  const teacherById = Object.fromEntries((teachers || []).map((t) => [t.id, t]))
  const roomById = Object.fromEntries((rooms || []).map((r) => [r.id, r]))
  const groupById = Object.fromEntries((groups || []).map((g) => [g.id, g]))

  const focusOptions =
    mode === 'teacher' ? teachers
    : mode === 'room' ? rooms
    : mode === 'class_group' ? groups
    : mode === 'course' ? courses : []

  const filtered = entries.filter((e) => mode === 'all' || e[mode] === focus)

  const chipLabel = (e) => {
    const parts = [`${e.course}${courseById[e.course] ? ` (${courseById[e.course].subject})` : ''}`]
    if (mode !== 'teacher' && e.teacher) parts.push(teacherById[e.teacher]?.name || e.teacher)
    if (mode !== 'room' && e.room) parts.push(roomById[e.room] ? e.room : e.room)
    if (mode !== 'class_group' && e.class_group) parts.push(groupById[e.class_group]?.name || e.class_group)
    return parts
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h3 className="text-sm font-semibold text-slate-800">Timetable</h3>
        <select value={mode} onChange={(e) => { setMode(e.target.value); setFocus('') }}
                className="rounded border border-slate-300 px-2 py-1 text-xs">
          {MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
        {mode !== 'all' && (
          <select value={focus} onChange={(e) => setFocus(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-xs">
            <option value="">— select —</option>
            {focusOptions.map((o) => <option key={o.id} value={o.id}>{o.name || o.id}</option>)}
          </select>
        )}
        {mode !== 'all' && !focus && (
          <span className="text-xs text-slate-400">Select an entity to filter.</span>
        )}
      </div>

      {filtered.length === 0 ? (
        <p className="text-xs text-slate-400">No sessions to display.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr>
                <th className="border border-slate-200 bg-slate-50 p-2"></th>
                {PERIODS.map((p) => (
                  <th key={p} className="border border-slate-200 bg-slate-50 p-2 font-semibold text-slate-700">
                    Period {p}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {DAYS.map((day) => (
                <tr key={day}>
                  <th className="border border-slate-200 bg-slate-50 p-2 font-semibold text-slate-700">{day}</th>
                  {PERIODS.map((p) => {
                    const cell = filtered.filter((e) => e.day === day && e.period === `Period ${p}`)
                    return (
                      <td key={p} className="border border-slate-200 p-1 align-top">
                        {cell.map((e, i) => (
                          <div key={i} style={{ backgroundColor: colorFor(e.course) }}
                               className="mb-1 rounded px-1.5 py-1 leading-snug last:mb-0">
                            <div className="font-semibold text-slate-800">{chipLabel(e)[0]}</div>
                            <div className="text-[11px] text-slate-600">{chipLabel(e).slice(1).join(' · ')}</div>
                          </div>
                        ))}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
