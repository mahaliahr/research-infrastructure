import { useState, useEffect } from 'react'

const API = 'http://localhost:8000'

const SESSION_TYPES = [
  'reading',
  'writing',
  'coding',
  'supervisor meeting',
  'thinking / planning',
  'literature review',
  'other'
]

export default function ActivityLog() {
  const [sessions, setSessions] = useState([])
  const [active, setActive] = useState(null)
  const [type, setType] = useState(SESSION_TYPES[0])
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchSessions()
    // restore any active session surviving a page refresh
    const stored = localStorage.getItem('active_session')
    if (stored) setActive(JSON.parse(stored))
  }, [])

  async function fetchSessions() {
    try {
      const res = await fetch(`${API}/sessions`)
      const data = await res.json()
      setSessions(data.sessions)
    } catch (e) {
      console.error('could not fetch sessions', e)
    } finally {
      setLoading(false)
    }
  }

async function startSession() {
  const started = new Date().toISOString()
  try {
    const res = await fetch(`${API}/sessions/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, note, started })
    })
    const data = await res.json()
    const session = { id: data.id, type, note, started }

    setActive(session)
    localStorage.setItem('active_session', JSON.stringify(session))
    setNote('')
  } catch (e) {
    console.error('could not start session', e)
  }
}

async function endSession() {
  const ended = new Date().toISOString()
  const duration = Math.round((new Date(ended) - new Date(active.started)) / 60000)
  try {
    await fetch(`${API}/sessions/end`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: active.id, ended, duration, started: active.started })
    })

    localStorage.removeItem('active_session')
    setActive(null)
    fetchSessions()
  } catch (e) {
    console.error('could not end session', e)
  }
}

  function formatTime(iso) {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  function formatDate(iso) {
    return new Date(iso).toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' })
  }

  return (
    <div>
      <h1>Activity Log</h1>

      <div className="card" style={{ marginBottom: 32 }}>
        {!active ? (
          <>
            <p className="label">what are you working on?</p>
            <div className="row" style={{ gap: 12, marginBottom: 12 }}>
              <select
                value={type}
                onChange={e => setType(e.target.value)}
                className="select"
              >
                {SESSION_TYPES.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <input
                className="input"
                placeholder="optional note..."
                value={note}
                onChange={e => setNote(e.target.value)}
              />
            </div>
            <button className="btn btn--start" onClick={startSession}>
              start session
            </button>
          </>
        ) : (
          <div className="active-session">
            <div className="active-session__indicator" />
            <div>
              <p className="active-session__type">{active.type}</p>
              {active.note && <p className="active-session__note">{active.note}</p>}
              <p className="active-session__time">started {formatTime(active.started)}</p>
            </div>
            <button className="btn btn--end" onClick={endSession}>
              end session
            </button>
          </div>
        )}
      </div>

      <div className="log">
        {loading && <p style={{ color: '#888', fontSize: 13 }}>loading...</p>}
        {!loading && sessions.length === 0 && (
          <p style={{ color: '#888', fontSize: 13 }}>no sessions yet</p>
        )}
        {sessions.map((s, i) => {
          const showDate = i === 0 || formatDate(s.started) !== formatDate(sessions[i - 1].started)
          return (
            <div key={s.id}>
              {showDate && (
                <p className="log__date">{formatDate(s.started)}</p>
              )}
              <div className="log__entry">
                <span className="log__type">{s.type}</span>
                {s.note && <span className="log__note">{s.note}</span>}
                <span className="log__meta">
                  {formatTime(s.started)} · {s.duration}m
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}