import { useState, useEffect } from 'react'

const API = 'http://localhost:8000'

export default function Mirror() {
  const [weekly, setWeekly] = useState([])
  const [daily, setDaily] = useState([])
  const [selectedWeek, setSelectedWeek] = useState(null)
  const [selectedDay, setSelectedDay] = useState(null)
  const [view, setView] = useState('weekly')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      fetch(`${API}/mirror/weekly`).then(r => r.json()),
      fetch(`${API}/mirror/daily`).then(r => r.json())
    ]).then(([w, d]) => {
      setWeekly(w.files || [])
      setDaily(d.files || [])
      if (w.files && w.files.length > 0) setSelectedWeek(w.files[0])
      if (d.files && d.files.length > 0) setSelectedDay(d.files[0])
      setLoading(false)
    }).catch(e => {
      setError('could not load mirror data')
      setLoading(false)
    })
  }, [])

  function parseListSection(text) {
    if (!text) return []
    return text.split('\n')
      .map(l => l.replace(/^-\s*/, '').trim())
      .filter(l => l && l !== 'none')
  }

  function renderDaily(file) {
    if (!file) return <p className="label">no daily file selected</p>
    const s = file.parsed
    return (
      <div style={{ maxWidth: 640 }}>
        <p className="label" style={{ marginBottom: 16, textAlign: 'left' }}>{file.date}</p>

        <div className="card" style={{ marginBottom: 16, textAlign: 'left' }}>
          <p className="label" style={{ marginBottom: 8 }}>notes created</p>
          {parseListSection(s.notes_created).length === 0
            ? <p style={{ color: '#888', fontSize: 13 }}>none</p>
            : parseListSection(s.notes_created).map((n, i) => (
                <p key={i} style={{ fontSize: 14, margin: '4px 0',
                  borderBottom: '1px solid #f0f0f0', paddingBottom: 4 }}>{n}</p>
              ))
          }
        </div>

        <div className="card" style={{ marginBottom: 16, textAlign: 'left' }}>
          <p className="label" style={{ marginBottom: 8 }}>notes edited</p>
          {parseListSection(s.notes_edited).length === 0
            ? <p style={{ color: '#888', fontSize: 13 }}>none</p>
            : parseListSection(s.notes_edited).map((n, i) => (
                <p key={i} style={{ fontSize: 14, margin: '4px 0',
                  borderBottom: '1px solid #f0f0f0', paddingBottom: 4 }}>{n}</p>
              ))
          }
        </div>

        <div className="card" style={{ marginBottom: 16, textAlign: 'left' }}>
          <p className="label" style={{ marginBottom: 8 }}>sessions</p>
          {parseListSection(s.sessions).length === 0
            ? <p style={{ color: '#888', fontSize: 13 }}>none</p>
            : parseListSection(s.sessions).map((n, i) => (
                <p key={i} style={{ fontSize: 14, margin: '4px 0',
                  borderBottom: '1px solid #f0f0f0', paddingBottom: 4 }}>{n}</p>
              ))
          }
        </div>

        <div className="card" style={{ textAlign: 'left' }}>
          <p className="label" style={{ marginBottom: 8 }}>orphans flagged</p>
          {parseListSection(s.orphans_flagged).length === 0
            ? <p style={{ color: '#888', fontSize: 13 }}>none</p>
            : parseListSection(s.orphans_flagged).map((n, i) => (
                <p key={i} style={{ fontSize: 13, color: '#888',
                  margin: '4px 0' }}>{n}</p>
              ))
          }
        </div>
      </div>
    )
  }

  function renderWeekly(file) {
    if (!file) return <p className="label">no weekly file yet</p>
    const s = file.parsed

    // split synthesis from grounded-in line
    const synthesisRaw = s.synthesis || ''
    const groundedMatch = synthesisRaw.match(/([\s\S]*?)\n\ngrounded in:(.+)/s)
    const synthesisText = groundedMatch
      ? groundedMatch[1].trim()
      : synthesisRaw.replace(/grounded in:.+$/s, '').trim()
    const groundedText = groundedMatch
      ? 'grounded in:' + groundedMatch[2].trim()
      : synthesisRaw.match(/grounded in:(.+)/s)
        ? 'grounded in:' + synthesisRaw.match(/grounded in:(.+)/s)[1].trim()
        : ''

    return (
      <div style={{ maxWidth: 640 }}>
        <p className="label" style={{ marginBottom: 16, textAlign: 'left' }}>{file.week}</p>

        <div className="card" style={{ marginBottom: 16, textAlign: 'left' }}>
          <p className="label" style={{ marginBottom: 8 }}>summary</p>
          {parseListSection(s.summary).map((n, i) => (
            <p key={i} style={{ fontSize: 14, margin: '3px 0',
              color: '#333' }}>{n}</p>
          ))}
        </div>

        <div className="card" style={{ marginBottom: 16, textAlign: 'left' }}>
          <p className="label" style={{ marginBottom: 8 }}>activity by day</p>
          {parseListSection(s.activity_by_day).map((n, i) => (
            <p key={i} style={{ fontSize: 13, margin: '3px 0',
              color: n.includes('no activity') ? '#aaa' : '#333' }}>{n}</p>
          ))}
        </div>

        <div className="card" style={{ marginBottom: 16, textAlign: 'left' }}>
          <p className="label" style={{ marginBottom: 8 }}>recurring terms</p>
          {parseListSection(s.recurring_terms).map((n, i) => {
            const parts = n.split(' — ')
            const term = parts[0]
            const count = parts[1]
            return (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between',
                alignItems: 'baseline', padding: '3px 0',
                borderBottom: i < parseListSection(s.recurring_terms).length - 1
                  ? '1px solid #f0f0f0' : 'none' }}>
                <span style={{ fontSize: 13 }}>{term}</span>
                <span style={{ fontSize: 12, color: '#aaa',
                  fontFamily: 'monospace' }}>{count}</span>
              </div>
            )
          })}
        </div>

        <div className="card" style={{ marginBottom: 16, textAlign: 'left' }}>
          <p className="label" style={{ marginBottom: 8 }}>orphans this week</p>
          {parseListSection(s.orphans_this_week).length === 0
            ? <p style={{ color: '#888', fontSize: 13 }}>none</p>
            : parseListSection(s.orphans_this_week).map((n, i) => (
                <p key={i} style={{ fontSize: 13, color: '#888',
                  margin: '3px 0' }}>{n}</p>
              ))
          }
        </div>

        <div className="card" style={{ marginBottom: 16, textAlign: 'left' }}>
          <p className="label" style={{ marginBottom: 8 }}>synthesis</p>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: '#333',
            margin: '0 0 12px 0' }}>{synthesisText}</p>
          {groundedText && (
            <p style={{ fontSize: 12, color: '#aaa', margin: 0,
              fontFamily: 'monospace' }}>{groundedText}</p>
          )}
        </div>

        <div className="card" style={{ textAlign: 'left' }}>
          <p className="label" style={{ marginBottom: 8 }}>generated prompt</p>
          <p style={{ fontSize: 14, lineHeight: 1.6, fontStyle: 'italic',
            color: '#333', margin: 0, textAlign: 'left' }}>
            {s.generated_prompt || 'unavailable'}
          </p>
        </div>
      </div>
    )
  }

  if (loading) return <div><h1>Mirror</h1><p className="label">loading...</p></div>
  if (error) return <div><h1>Mirror</h1><p className="label">{error}</p></div>

  return (
    <div style={{ padding: '0 0 0 8px', textAlign: 'left' }}>
      <h1>Mirror</h1>

      <div className="row" style={{ gap: 8, marginBottom: 24 }}>
        <button
          className={`btn ${view === 'weekly' ? 'btn--start' : ''}`}
          onClick={() => setView('weekly')}
        >
          weekly
        </button>
        <button
          className={`btn ${view === 'daily' ? 'btn--start' : ''}`}
          onClick={() => setView('daily')}
        >
          daily
        </button>
      </div>

      {view === 'weekly' && (
        <div>
          <div className="row" style={{ gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
            {weekly.map(f => (
              <button
                key={f.week}
                className={`btn ${selectedWeek?.week === f.week ? 'btn--start' : ''}`}
                onClick={() => setSelectedWeek(f)}
              >
                {f.week}
              </button>
            ))}
          </div>
          {renderWeekly(selectedWeek)}
        </div>
      )}

      {view === 'daily' && (
        <div>
          <div className="row" style={{ gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
            {daily.map(f => (
              <button
                key={f.date}
                className={`btn ${selectedDay?.date === f.date ? 'btn--start' : ''}`}
                onClick={() => setSelectedDay(f)}
              >
                {f.date}
              </button>
            ))}
          </div>
          {renderDaily(selectedDay)}
        </div>
      )}
    </div>
  )
}
