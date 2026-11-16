const FIELDS = [
  { key: 'balance_weight', label: 'Balance weight (teacher load)', min: 0, max: 20, step: 0.5 },
  { key: 'gap_weight', label: 'Gap weight (idle periods)', min: 0, max: 20, step: 0.5 },
  { key: 'spread_weight', label: 'Spread weight (sessions per day)', min: 0, max: 20, step: 0.5 },
  { key: 'time_limit_seconds', label: 'Solver time limit (s)', min: 1, max: 120, step: 1 },
]

export default function PreferencesPanel({ preferences, onChange }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold text-slate-800">Optimization preferences</h3>
      <div className="space-y-3">
        {FIELDS.map((f) => (
          <label key={f.key} className="block">
            <div className="mb-1 flex justify-between text-xs">
              <span className="font-medium text-slate-600">{f.label}</span>
              <span className="text-slate-900">{preferences[f.key]}</span>
            </div>
            <input type="range" min={f.min} max={f.max} step={f.step}
                   value={preferences[f.key] ?? 0}
                   onChange={(e) => onChange({ ...preferences, [f.key]: Number(e.target.value) })}
                   className="w-full accent-indigo-600" />
          </label>
        ))}
      </div>
      <p className="mt-3 text-[11px] leading-snug text-slate-400">
        Gap weight penalizes idle periods between classes on the same day; spread weight
        encourages distributing a course's sessions across the week; balance weight evens out
        teacher weekly loads.
      </p>
    </section>
  )
}
