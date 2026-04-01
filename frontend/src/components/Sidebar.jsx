import React from 'react'
import './Sidebar.css'

const NAV = [
  { id: 'map',          label: 'Ground Track',    icon: 'G' },
  { id: 'fleet',        label: 'Fleet Health',     icon: 'F' },
  { id: 'timeline',     label: 'Maneuver Timeline',icon: 'T' },
  { id: 'conjunctions', label: 'Conjunctions',     icon: 'C' },
  { id: 'perf',         label: 'Performance',      icon: 'P' },
  { id: 'demo',         label: '⭐ Demo Mode',       icon: '▶' },
]

export default function Sidebar({ activeView, setActiveView, status, conjunctions }) {
  const critCount = conjunctions.filter(c => c.risk_level === 'CRITICAL').length
  const warnCount = conjunctions.filter(c => c.risk_level === 'WARNING').length

  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        {NAV.map(item => (
          <button
            key={item.id}
            className={`nav-item ${activeView === item.id ? 'nav-active' : ''}`}
            onClick={() => setActiveView(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
            {item.id === 'conjunctions' && critCount > 0 && (
              <span className="nav-badge nav-badge-crit">{critCount}</span>
            )}
            {item.id === 'conjunctions' && warnCount > 0 && critCount === 0 && (
              <span className="nav-badge nav-badge-warn">{warnCount}</span>
            )}
          </button>
        ))}
      </nav>

      {status && (
        <div className="sidebar-stats">
          <div className="stat-row">
            <span className="stat-key">Sim Time</span>
            <span className="stat-val mono">
              {status.current_time
                ? new Date(status.current_time).toUTCString().slice(5, 22)
                : '—'}
            </span>
          </div>
          <div className="stat-row">
            <span className="stat-key">Fleet Fuel</span>
            <span className="stat-val mono">
              {status.total_fuel_remaining_kg != null
                ? `${status.total_fuel_remaining_kg.toFixed(0)} kg`
                : '—'}
            </span>
          </div>
          <div className="stat-row">
            <span className="stat-key">Avg Fuel</span>
            <span className="stat-val mono">
              {status.avg_fuel_fraction != null
                ? `${(status.avg_fuel_fraction * 100).toFixed(1)}%`
                : '—'}
            </span>
          </div>
          <div className="stat-row">
            <span className="stat-key">Total dV</span>
            <span className="stat-val mono">
              {status.total_dv_km_s != null
                ? `${(status.total_dv_km_s * 1000).toFixed(2)} m/s`
                : '—'}
            </span>
          </div>
          <div className="stat-row">
            <span className="stat-key">EOL Sats</span>
            <span className={`stat-val mono ${status.satellites_eol > 0 ? 'text-eol' : ''}`}>
              {status.satellites_eol ?? '—'}
            </span>
          </div>
        </div>
      )}
    </aside>
  )
}
