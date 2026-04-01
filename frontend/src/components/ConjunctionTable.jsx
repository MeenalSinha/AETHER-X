import React from 'react'
import './ConjunctionTable.css'

const RISK_ORDER = { CRITICAL: 0, WARNING: 1, ADVISORY: 2 }

function riskBadge(level) {
  if (level === 'CRITICAL') return <span className="badge badge-crit">CRITICAL</span>
  if (level === 'WARNING')  return <span className="badge badge-warn">WARNING</span>
  return <span className="badge badge-blue">ADVISORY</span>
}

export default function ConjunctionTable({ conjunctions, onSelect, selectedSat, full }) {
  const sorted = [...conjunctions].sort(
    (a, b) => (RISK_ORDER[a.risk_level] ?? 3) - (RISK_ORDER[b.risk_level] ?? 3)
  )

  return (
    <div className={`conj-panel panel ${full ? 'conj-full' : ''}`}>
      <div className="panel-header">
        Active Conjunctions
        <span className="text-muted mono" style={{ fontSize: 10 }}>
          {conjunctions.length} events
        </span>
      </div>

      {sorted.length === 0 ? (
        <div className="conj-empty">No conjunction warnings. Fleet is clear.</div>
      ) : (
        <div className="conj-table-wrap">
          <table className="conj-table">
            <thead>
              <tr>
                <th>Risk</th>
                <th>Satellite</th>
                <th>Debris</th>
                <th>Miss Dist</th>
                <th>TCA</th>
                <th>Current Dist</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((c, i) => (
                <tr
                  key={i}
                  className={`conj-row ${selectedSat === c.satellite_id ? 'conj-selected' : ''} ${c.risk_level === 'CRITICAL' ? 'conj-crit' : ''}`}
                  onClick={() => onSelect(c.satellite_id)}
                >
                  <td>{riskBadge(c.risk_level)}</td>
                  <td className="mono">{c.satellite_id}</td>
                  <td className="mono text-muted">{c.debris_id}</td>
                  <td className="mono">
                    <span style={{ color: c.min_distance_km < 0.1 ? 'var(--crit)' : c.min_distance_km < 1 ? 'var(--warn)' : 'var(--text-primary)' }}>
                      {c.min_distance_km < 1
                        ? `${(c.min_distance_km * 1000).toFixed(0)} m`
                        : `${c.min_distance_km.toFixed(2)} km`}
                    </span>
                  </td>
                  <td className="mono text-muted">
                    {c.tca_seconds < 3600
                      ? `${(c.tca_seconds / 60).toFixed(0)} min`
                      : `${(c.tca_seconds / 3600).toFixed(1)} hr`}
                  </td>
                  <td className="mono text-muted">{c.current_distance_km?.toFixed(1)} km</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
