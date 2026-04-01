import React, { useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, CartesianGrid, Legend
} from 'recharts'
import './FleetHealthPanel.css'

function fuelColor(pct) {
  if (pct < 5)  return 'var(--crit)'
  if (pct < 20) return 'var(--warn)'
  return 'var(--ok)'
}

export default function FleetHealthPanel({ fleetHealth, snapshot, onSelect, selectedSat }) {
  const [sortBy, setSortBy] = useState('id')

  const sorted = [...fleetHealth].sort((a, b) => {
    if (sortBy === 'fuel') return a.fuel_pct - b.fuel_pct
    if (sortBy === 'dv')   return b.total_dv_ms - a.total_dv_ms
    return a.id.localeCompare(b.id)
  })

  // dV vs collisions avoided scatter data (proxy: fewer warnings = more avoided)
  const dvData = fleetHealth.map(s => ({
    id: s.id,
    dv: parseFloat(s.total_dv_ms?.toFixed(3) || 0),
    uptime: parseFloat(s.uptime_h?.toFixed(2) || 0),
  }))

  // Fuel histogram bins
  const bins = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
  const fuelHist = bins.slice(0, -1).map((b, i) => ({
    range: `${b}-${bins[i+1]}%`,
    count: fleetHealth.filter(s => s.fuel_pct >= b && s.fuel_pct < bins[i+1]).length,
  }))

  return (
    <div className="fleet-panel">
      {/* Controls */}
      <div className="fleet-controls panel">
        <span className="panel-header" style={{ border: 'none', padding: 0 }}>Fleet Health Dashboard</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className="sort-label">Sort by:</span>
          {['id', 'fuel', 'dv'].map(s => (
            <button
              key={s}
              className={`sort-btn ${sortBy === s ? 'sort-active' : ''}`}
              onClick={() => setSortBy(s)}
            >
              {s === 'id' ? 'ID' : s === 'fuel' ? 'Fuel' : 'Total dV'}
            </button>
          ))}
        </div>
      </div>

      <div className="fleet-body">
        {/* Satellite grid */}
        <div className="sat-grid panel">
          <div className="panel-header">
            Satellites
            <span className="text-muted">
              {fleetHealth.filter(s => s.status === 'EOL').length} EOL / {fleetHealth.length} total
            </span>
          </div>
          <div className="sat-list">
            {sorted.map(sat => (
              <div
                key={sat.id}
                className={`sat-row ${selectedSat === sat.id ? 'sat-selected' : ''} ${sat.status === 'EOL' ? 'sat-eol' : ''}`}
                onClick={() => onSelect(sat.id === selectedSat ? null : sat.id)}
              >
                <div className="sat-id mono">{sat.id}</div>

                <div className="sat-fuel-wrap">
                  <div className="fuel-bar-wrap" style={{ width: '100%' }}>
                    <div
                      className="fuel-bar-fill"
                      style={{
                        width: `${sat.fuel_pct}%`,
                        background: fuelColor(sat.fuel_pct),
                      }}
                    />
                  </div>
                  <span className="fuel-pct mono">{sat.fuel_pct?.toFixed(1)}%</span>
                </div>

                <div className="sat-meta">
                  <span className={`badge badge-${
                    sat.status === 'EOL' ? 'eol' :
                    sat.in_box ? 'ok' : 'warn'
                  }`}>
                    {sat.status === 'EOL' ? 'EOL' : sat.in_box ? 'IN-BOX' : 'DRIFT'}
                  </span>
                  <span className="mono text-muted">{sat.total_dv_ms?.toFixed(2)}m/s</span>
                  <span className="mono text-muted">{sat.uptime_h?.toFixed(1)}h</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Charts */}
        <div className="fleet-charts">
          <div className="panel chart-panel">
            <div className="panel-header">Fuel Distribution</div>
            <div className="chart-body">
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={fuelHist} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="range" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} />
                  <YAxis tick={{ fontSize: 9, fill: 'var(--text-muted)' }} />
                  <Tooltip
                    contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 11 }}
                  />
                  <Bar dataKey="count" fill="var(--accent-blue)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel chart-panel">
            <div className="panel-header">dV Usage vs Uptime</div>
            <div className="chart-body">
              <ResponsiveContainer width="100%" height={180}>
                <ScatterChart margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="dv" name="dV (m/s)" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} label={{ value: 'dV m/s', position: 'insideBottom', offset: -2, fontSize: 9 }} />
                  <YAxis dataKey="uptime" name="Uptime (h)" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} />
                  <Tooltip
                    contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 11 }}
                    cursor={{ strokeDasharray: '3 3' }}
                  />
                  <Scatter data={dvData} fill="var(--accent-teal)" opacity={0.7} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
