import React, { useMemo } from 'react'
import './ManeuverTimeline.css'

const COOLDOWN_S = 600
const COLORS = {
  evasion:  '#1a56db',
  recovery: '#0d9488',
  eol:      '#7c3aed',
  cooldown: '#e5e7eb',
}

function burnType(burn_id) {
  if (burn_id?.startsWith('EVA')) return 'evasion'
  if (burn_id?.startsWith('REC')) return 'recovery'
  if (burn_id?.startsWith('EOL')) return 'eol'
  return 'evasion'
}

export default function ManeuverTimeline({ maneuverLog, snapshot, status }) {
  const now = status?.current_time ? new Date(status.current_time) : new Date()

  // Group log by satellite
  const bySat = useMemo(() => {
    const map = {}
    for (const entry of maneuverLog) {
      if (!map[entry.satellite_id]) map[entry.satellite_id] = []
      map[entry.satellite_id].push(entry)
    }
    return map
  }, [maneuverLog])

  // Pending burns from snapshot
  const pendingBySat = useMemo(() => {
    const map = {}
    for (const sat of (snapshot?.satellites || [])) {
      if (sat.pending_burns?.length > 0) {
        map[sat.id] = sat.pending_burns
      }
    }
    return map
  }, [snapshot])

  const sats = Array.from(new Set([
    ...Object.keys(bySat),
    ...Object.keys(pendingBySat),
  ])).sort()

  // Timeline window: 2 hours before now to 4 hours after
  const winStart = new Date(now.getTime() - 2 * 3600 * 1000)
  const winEnd   = new Date(now.getTime() + 4 * 3600 * 1000)
  const winMs    = winEnd - winStart

  function toX(t) {
    return Math.max(0, Math.min(100, ((new Date(t) - winStart) / winMs) * 100))
  }
  function widthPct(startT, durationMs) {
    return Math.max(0.2, (durationMs / winMs) * 100)
  }

  const nowX = toX(now)

  // Time ticks
  const ticks = []
  for (let i = 0; i <= 6; i++) {
    const t = new Date(winStart.getTime() + i * (winMs / 6))
    ticks.push({ x: (i / 6) * 100, label: t.toUTCString().slice(17, 22) + 'Z' })
  }

  if (sats.length === 0) {
    return (
      <div className="timeline-panel panel">
        <div className="panel-header">Maneuver Timeline</div>
        <div className="timeline-empty">No maneuvers logged yet. Run a simulation step to generate burns.</div>
      </div>
    )
  }

  return (
    <div className="timeline-panel panel">
      <div className="panel-header">
        Maneuver Timeline (Gantt)
        <span className="text-muted" style={{ fontSize: 10 }}>
          Window: {winStart.toUTCString().slice(5, 22)} — {winEnd.toUTCString().slice(5, 22)}
        </span>
      </div>

      {/* Legend */}
      <div className="timeline-legend">
        {Object.entries(COLORS).map(([k, c]) => (
          <span key={k} className="tl-legend-item">
            <span className="tl-legend-swatch" style={{ background: c }} />
            {k}
          </span>
        ))}
      </div>

      {/* Time axis */}
      <div className="tl-axis">
        {ticks.map((t, i) => (
          <div key={i} className="tl-tick" style={{ left: `${t.x}%` }}>
            <span className="tl-tick-label mono">{t.label}</span>
          </div>
        ))}
        {/* NOW line */}
        <div className="tl-now-line" style={{ left: `${nowX}%` }}>
          <span className="tl-now-label">NOW</span>
        </div>
      </div>

      {/* Rows */}
      <div className="tl-rows">
        {sats.map(satId => {
          const executed = bySat[satId] || []
          const pending  = pendingBySat[satId] || []

          return (
            <div key={satId} className="tl-row">
              <div className="tl-sat-label mono">{satId}</div>
              <div className="tl-track">
                {/* NOW line on track */}
                <div className="tl-now-track" style={{ left: `${nowX}%` }} />

                {/* Executed burns */}
                {executed.map((b, i) => {
                  const t    = new Date(b.time)
                  const x    = toX(t)
                  const type = burnType(b.burn_id)
                  const coolX = toX(new Date(t.getTime() + COOLDOWN_S * 1000))
                  const coolW = widthPct(t, COOLDOWN_S * 1000)

                  return (
                    <React.Fragment key={b.burn_id + i}>
                      {/* Burn block */}
                      <div
                        className="tl-burn"
                        style={{ left: `${x}%`, background: COLORS[type] }}
                        title={`${b.burn_id} | ${b.dv_km_s ? (b.dv_km_s * 1000).toFixed(3) : '?'} m/s | ${b.time}`}
                      />
                      {/* Cooldown */}
                      <div
                        className="tl-cooldown"
                        style={{ left: `${x}%`, width: `${coolW}%` }}
                        title={`Cooldown 600s`}
                      />
                    </React.Fragment>
                  )
                })}

                {/* Pending burns */}
                {pending.map((b, i) => {
                  const t    = new Date(b.burn_time)
                  const x    = toX(t)
                  const type = burnType(b.burn_id)
                  return (
                    <div
                      key={'p' + i}
                      className="tl-burn tl-burn-pending"
                      style={{ left: `${x}%`, borderColor: COLORS[type] }}
                      title={`[Pending] ${b.burn_id} | ${b.dv_ms} m/s`}
                    />
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
