import React, { useState } from 'react'
import './Header.css'

const STEP_OPTIONS = [
  { label: '1 min',  value: 60 },
  { label: '10 min', value: 600 },
  { label: '1 hr',   value: 3600 },
  { label: '6 hr',   value: 21600 },
  { label: '24 hr',  value: 86400 },
]

export default function Header({ connected, status, stepping, lastStep, onStep, onRefresh }) {
  const [stepSec, setStepSec] = useState(3600)

  return (
    <header className="site-header">
      <div className="header-brand">
        <span className="header-logo">AX</span>
        <div className="header-title-group">
          <span className="header-title">AETHER-X</span>
          <span className="header-sub">Autonomous Constellation Manager</span>
        </div>
      </div>

      <div className="header-status">
        {status && (
          <>
            <div className="status-chip">
              <span className="status-label">Satellites</span>
              <span className="status-val mono">{status.satellites_nominal ?? status.satellites ?? '—'}</span>
            </div>
            <div className="status-chip">
              <span className="status-label">Debris</span>
              <span className="status-val mono">{status.debris?.toLocaleString() ?? '—'}</span>
            </div>
            <div className="status-chip warn-chip">
              <span className="status-label">Warnings</span>
              <span className="status-val mono">{status.active_warnings ?? '—'}</span>
            </div>
            <div className="status-chip crit-chip">
              <span className="status-label">Critical</span>
              <span className="status-val mono">{status.critical_warnings ?? '—'}</span>
            </div>
          </>
        )}
      </div>

      <div className="header-controls">
        <span className={`conn-indicator ${connected ? 'conn-ok' : 'conn-err'}`}>
          <span className={connected ? 'live-dot' : 'dead-dot'} />
          {connected ? 'LIVE' : 'OFFLINE'}
        </span>

        <select
          className="step-select"
          value={stepSec}
          onChange={e => setStepSec(Number(e.target.value))}
        >
          {STEP_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <button
          className="btn-step"
          onClick={() => onStep(stepSec)}
          disabled={stepping || !connected}
        >
          {stepping ? 'Stepping...' : 'Step Forward'}
        </button>

        <button className="btn-refresh" onClick={onRefresh} title="Refresh">
          Refresh
        </button>
      </div>
    </header>
  )
}
