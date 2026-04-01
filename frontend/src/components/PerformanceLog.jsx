import React from 'react'
import {
  LineChart, Line, BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import './PerformanceLog.css'

export default function PerformanceLog({ performance }) {
  const chartData = performance.map((p, i) => ({
    tick: i + 1,
    elapsed_ms: p.elapsed_ms,
    kdtree_ms: p.kdtree_build_ms,
    conjunctions: p.conjunctions,
    maneuvers: p.maneuvers_executed,
    cumulative_dv_km_s: p.cumulative_dv_km_s || 0,
    collisions_avoided: p.collisions_avoided || 0,
  }))

  const avgElapsed = performance.length
    ? (performance.reduce((s, p) => s + p.elapsed_ms, 0) / performance.length).toFixed(1)
    : '—'
  const totalManeuvers = performance.reduce((s, p) => s + (p.maneuvers_executed || 0), 0)
  const maxConj = Math.max(...performance.map(p => p.conjunctions || 0), 0)

  return (
    <div className="perf-panel">
      {/* Summary cards */}
      <div className="perf-cards">
        <div className="perf-card panel">
          <div className="perf-card-val mono">{avgElapsed}<span className="perf-unit">ms</span></div>
          <div className="perf-card-label">Avg Step Time</div>
        </div>
        <div className="perf-card panel">
          <div className="perf-card-val mono">{totalManeuvers}</div>
          <div className="perf-card-label">Total Maneuvers</div>
        </div>
        <div className="perf-card panel">
          <div className="perf-card-val mono">{maxConj}</div>
          <div className="perf-card-label">Peak Conjunctions</div>
        </div>
        <div className="perf-card panel">
          <div className="perf-card-val mono">{performance.length}</div>
          <div className="perf-card-label">Steps Run</div>
        </div>
      </div>

      {performance.length === 0 ? (
        <div className="panel perf-empty">
          No performance data yet. Run simulation steps to populate this view.
        </div>
      ) : (
        <div className="perf-charts">
          {/* Step timing */}
          <div className="panel perf-chart-panel">
            <div className="panel-header">Step Execution Time (ms)</div>
            <div className="perf-chart-body">
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData} margin={{ top: 8, right: 16, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="tick" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} label={{ value: 'Step', position: 'insideBottom', offset: -2, fontSize: 9 }} />
                  <YAxis tick={{ fontSize: 9, fill: 'var(--text-muted)' }} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 11 }} />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Line type="monotone" dataKey="elapsed_ms" stroke="var(--accent-blue)" dot={false} strokeWidth={2} name="Total (ms)" />
                  <Line type="monotone" dataKey="kdtree_ms" stroke="var(--accent-teal)" dot={false} strokeWidth={1.5} name="KD-Tree (ms)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Conjunctions + maneuvers */}
          <div className="panel perf-chart-panel">
            <div className="panel-header">Conjunctions Detected &amp; Maneuvers Executed</div>
            <div className="perf-chart-body">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chartData} margin={{ top: 8, right: 16, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="tick" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} />
                  <YAxis tick={{ fontSize: 9, fill: 'var(--text-muted)' }} />
                  <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 11 }} />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Bar dataKey="conjunctions" fill="var(--warn)" radius={[2,2,0,0]} name="Conjunctions" />
                  <Bar dataKey="maneuvers"    fill="var(--accent-blue)" radius={[2,2,0,0]} name="Maneuvers" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Scatter Plot: Δv Cost vs Collisions Avoided */}
          <div className="panel perf-chart-panel">
            <div className="panel-header">Efficiency: Cost (∆v) vs Outcomes (Collisions Avoided)</div>
            <div className="perf-chart-body">
              <ResponsiveContainer width="100%" height={200}>
                <ScatterChart margin={{ top: 8, right: 16, left: -10, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis type="number" dataKey="collisions_avoided" name="Collisions Avoided" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} label={{ value: 'Collisions Avoided', position: 'insideBottom', offset: -5, fontSize: 10 }} allowDecimals={false} />
                  <YAxis type="number" dataKey="cumulative_dv_km_s" name="Total ∆v (km/s)" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} />
                  <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 11 }} />
                  <Scatter name="Efficiency Frontier" data={chartData} fill="var(--accent-blue)" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Raw log table */}
          <div className="panel perf-log-panel">
            <div className="panel-header">Raw Performance Log</div>
            <div className="perf-table-wrap">
              <table className="perf-table">
                <thead>
                  <tr>
                    <th>Step</th>
                    <th>Sim Time</th>
                    <th>Step Size</th>
                    <th>Elapsed</th>
                    <th>KD-Tree</th>
                    <th>Conjunctions</th>
                    <th>Maneuvers</th>
                  </tr>
                </thead>
                <tbody>
                  {[...performance].reverse().map((p, i) => (
                    <tr key={i}>
                      <td className="mono">{performance.length - i}</td>
                      <td className="mono text-muted">{p.time ? new Date(p.time).toUTCString().slice(5, 22) : '—'}</td>
                      <td className="mono">{p.step_s}s</td>
                      <td className="mono" style={{ color: p.elapsed_ms > 5000 ? 'var(--warn)' : 'var(--ok)' }}>
                        {p.elapsed_ms?.toFixed(0)}ms
                      </td>
                      <td className="mono text-muted">{p.kdtree_build_ms?.toFixed(1)}ms</td>
                      <td className="mono">{p.conjunctions}</td>
                      <td className="mono">{p.maneuvers_executed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
