import { useState } from 'react'
import { DAYS } from '../api'

const inputCls =
  'w-full rounded border border-slate-300 px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none'

function initDraft(fields) {
  const d = {}
  for (const f of fields) {
    if (f.type === 'checkbox') d[f.key] = false
    else if (f.type === 'days' || f.type === 'teachers') d[f.key] = []
    else if (f.type === 'number') d[f.key] = f.default ?? ''
    else d[f.key] = f.default ?? ''
  }
  return d
}

function itemToDraft(item, fields) {
  const d = {}
  for (const f of fields) {
    const v = item[f.key]
    if (f.type === 'tags') d[f.key] = (v || []).join(', ')
    else if (f.type === 'number') d[f.key] = v ?? ''
    else if (f.type === 'checkbox') d[f.key] = Boolean(v)
    else if (f.type === 'days' || f.type === 'teachers') d[f.key] = v || []
    else d[f.key] = v ?? ''
  }
  return d
}

function draftToItem(draft, fields) {
  const item = {}
  for (const f of fields) {
    const v = draft[f.key]
    if (f.type === 'tags') item[f.key] = v.split(',').map((s) => s.trim()).filter(Boolean)
    else if (f.type === 'number')
      item[f.key] = v === '' || v === null ? (f.nullable ? null : 0) : Number(v)
    else if (f.type === 'checkbox') item[f.key] = Boolean(v)
    else item[f.key] = v
  }
  return item
}

function Field({ field, value, onChange, options }) {
  if (field.type === 'checkbox') {
    return (
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} />
        {field.label}
      </label>
    )
  }
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">{field.label}</span>
      {field.type === 'number' && (
        <input type="number" className={inputCls} value={value}
               placeholder={field.placeholder} onChange={(e) => onChange(e.target.value)} />
      )}
      {field.type === 'tags' && (
        <input type="text" className={inputCls} value={value}
               placeholder={field.placeholder} onChange={(e) => onChange(e.target.value)} />
      )}
      {field.type === 'days' && (
        <div className="flex flex-wrap gap-2">
          {DAYS.map((day) => (
            <label key={day} className="flex items-center gap-1 text-xs">
              <input type="checkbox" checked={value.includes(day)}
                     onChange={(e) => onChange(e.target.checked ? [...value, day] : value.filter((d) => d !== day))} />
              {day}
            </label>
          ))}
        </div>
      )}
      {field.type === 'teachers' && (
        <div className="flex flex-wrap gap-2">
          {(options.teachers || []).map((t) => (
            <label key={t} className="flex items-center gap-1 text-xs">
              <input type="checkbox" checked={value.includes(t)}
                     onChange={(e) => onChange(e.target.checked ? [...value, t] : value.filter((d) => d !== t))} />
              {t}
            </label>
          ))}
        </div>
      )}
      {field.type === 'select' && (
        <select className={inputCls} value={value} onChange={(e) => onChange(e.target.value)}>
          {field.none && <option value="">{field.noneLabel || 'None'}</option>}
          {(field.options || []).map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      )}
      {(!field.type || field.type === 'text') && (
        <input type="text" className={inputCls} value={value}
               placeholder={field.placeholder} onChange={(e) => onChange(e.target.value)} />
      )}
    </label>
  )
}

export default function EntityEditor({ title, fields, items, onChange, options, keyField = 'id' }) {
  const [draft, setDraft] = useState(null) // null = form closed
  const [editingIdx, setEditingIdx] = useState(null)
  const [error, setError] = useState('')

  const openAdd = () => { setDraft(initDraft(fields)); setEditingIdx(null); setError('') }
  const openEdit = (idx) => { setDraft(itemToDraft(items[idx], fields)); setEditingIdx(idx); setError('') }
  const close = () => { setDraft(null); setEditingIdx(null); setError('') }

  const submit = () => {
    const item = draftToItem(draft, fields)
    if (!item[keyField]) { setError(`${keyField} is required`); return }
    const others = items.filter((_, i) => i !== editingIdx)
    if (others.some((it) => it[keyField] === item[keyField])) {
      setError(`Duplicate ${keyField}: "${item[keyField]}"`)
      return
    }
    const next = [...items]
    if (editingIdx === null) next.push(item)
    else next[editingIdx] = item
    onChange(next)
    close()
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        {!draft && (
          <button onClick={openAdd}
                  className="rounded bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700">
            + Add
          </button>
        )}
      </div>

      {items.length === 0 && !draft && (
        <p className="text-xs text-slate-400">Nothing added yet.</p>
      )}

      {items.length > 0 && (
        <ul className="mb-3 space-y-1">
          {items.map((it, idx) => (
            <li key={it[keyField] ?? idx}
                className="flex items-center justify-between rounded bg-slate-50 px-2 py-1.5 text-xs">
              <span className="truncate text-slate-700">{it.id}{it.name ? ` — ${it.name}` : ''}</span>
              <span className="flex shrink-0 gap-1">
                <button onClick={() => openEdit(idx)} className="text-indigo-600 hover:underline">Edit</button>
                <button onClick={() => onChange(items.filter((_, i) => i !== idx))}
                        className="text-rose-600 hover:underline">Delete</button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {draft && (
        <div className="rounded border border-indigo-200 bg-indigo-50/50 p-3">
          <div className="grid grid-cols-2 gap-3">
            {fields.map((f) => (
              <Field key={f.key} field={f} value={draft[f.key]}
                     options={options}
                     onChange={(v) => setDraft({ ...draft, [f.key]: v })} />
            ))}
          </div>
          {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
          <div className="mt-3 flex gap-2">
            <button onClick={submit}
                    className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700">
              {editingIdx === null ? 'Add' : 'Update'}
            </button>
            <button onClick={close} className="rounded border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-100">
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
