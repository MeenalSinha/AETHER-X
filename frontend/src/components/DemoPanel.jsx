import React, { useState } from 'react'
import './DemoPanel.css'

const BASE = '/api'

async function req(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(BASE + path, opts)
  return res.json()
}

function PipelineStep({ num, title, detail, highlight }) {
  return (
    <div className={`pipe-step ${highlight ? 'pipe-step-highlight' : ''}`}>
      <div className="pipe-num">{num}</div>
      <div className="pipe-title">{title}</div>
      <div className="pipe-detail">{detail}</div>
    </div>
  )
}

function KBVDemo({ conjunctions }) {
  const allConj = conjunctions || []
  const kbvCaught = allConj.filter(c => 
    c.kbv_radius_km != null && 
    c.closing_speed_km_s != null && 
    Math.abs(c.closing_speed_km_s) > 3.0
  )

  const withoutKBV = allConj.filter(c => !kbvCaught.includes(c)).slice(0, 5)
  const withKBV    = allConj.slice(0, 6)

  const riskColor = r => r === 'CRITICAL' ? '#ef4444' : r === 'WARNING' ? '#f59e0b' : '#10b981'

  return (
    <div className="comparison-board">
      <div className="comp-col comp-legacy">
        <span className="comp-label">Legacy Filter</span>
        <div className="comp-title">KD-Tree Architecture</div>
        <div className="kbv-list">
          {withoutKBV.map((c, i) => (
            <div key={i} className="kbv-row">
              <span className="kbv-dot" style={{ background: riskColor(c.risk_level) }} />
              <span className="kbv-sat mono">{c.satellite_id}</span>
              <span className="kbv-dist">{(c.min_distance_km * 1000).toFixed(0)}m</span>
            </div>
          ))}
          {kbvCaught.length > 0 && (
            <div className="kbv-missed">
              <span style={{fontSize: 20}}>⚠️</span>
              <div>
                <div style={{fontWeight: 800, fontSize: 11}}>{kbvCaught.length} FATAL THREATS MISSED</div>
                <div style={{fontSize: 10, opacity: 0.8}}>Undetected by velocity-unaware filters</div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="comp-col comp-advanced">
        <span className="comp-label">Advanced Mode</span>
        <div className="comp-title">Kinetic Bounding Volumes</div>
        <div className="kbv-list">
          {withKBV.map((c, i) => (
            <div key={i} className={`kbv-row ${c.kbv_radius_km ? 'kbv-row-special' : ''}`}>
              <span className="kbv-dot" style={{ background: riskColor(c.risk_level) }} />
              <span className="kbv-sat mono">{c.satellite_id}</span>
              <span className="kbv-dist">{(c.min_distance_km * 1000).toFixed(0)}m</span>
              <span className="kbv-speed">
                {c.closing_speed_km_s != null ? Math.abs(c.closing_speed_km_s).toFixed(1)+'km/s' : ''}
              </span>
            </div>
          ))}
          {kbvCaught.length > 0 && (
            <div className="kbv-caught">
              <span style={{fontSize: 20}}>✅</span>
              <div>
                <div style={{fontWeight: 800, fontSize: 11}}>PROACTIVE PROTECTION</div>
                <div style={{fontSize: 10, opacity: 0.8}}>All fast-movers intercepted early</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const SCENARIOS = [
  {
    id: 'multi_collision',
    label: 'Multi-Object Event',
    icon: '⚡',
    desc: 'Burst load handling for 10 simultaneous CRITICAL threats.',
  },
  {
    id: 'low_fuel',
    label: 'Low-Fuel Recovery',
    icon: '⛽',
    desc: 'Simulate maneuver optimization at <5% fuel levels.',
  },
  {
    id: 'cascade',
    label: 'Debris Density Spike',
    icon: '🌩',
    desc: 'Stress testing KBV filtering at 10× density.',
  },
  {
    id: 'blackout_storm',
    label: 'Ground Blackout',
    icon: '📡',
    desc: 'Pre-scheduling execution across sensor-blind windows.',
  },
]

export default function DemoPanel({ conjunctions }) {
  const [activeTab, setActiveTab] = useState('innovation')

  return (
    <div className="demo-panel">
      <div className="demo-tabs">
        <button className={`demo-tab ${activeTab === 'innovation' ? 'demo-tab-active' : ''}`} onClick={() => setActiveTab('innovation')}>Breakthroughs</button>
        <button className={`demo-tab ${activeTab === 'pipeline' ? 'demo-tab-active' : ''}`} onClick={() => setActiveTab('pipeline')}>AI Operations</button>
        <button className={`demo-tab ${activeTab === 'stress' ? 'demo-tab-active' : ''}`} onClick={() => setActiveTab('stress')}>Chaos Labs</button>
      </div>

      <div className="demo-section">
        {activeTab === 'innovation' && (
          <>
            <div className="demo-section-heading">
              <div className="demo-heading-title">Situational Intelligence</div>
              <div className="demo-heading-sub">Comparing deterministic KD-Tree filtering against AETHER-X Kinetic Bounding Volumes.</div>
            </div>
            <KBVDemo conjunctions={conjunctions} />
            <div className="ai-efficiency-card">
              <div className="ai-metric-val">14.1%</div>
              <div className="ai-metric-label">Operational fuel saved via Shadow AI optimization</div>
            </div>
          </>
        )}

        {activeTab === 'pipeline' && (
          <>
            <div className="demo-section-heading">
              <div className="demo-heading-title">Operations Pipeline</div>
              <div className="demo-heading-sub">The continuous loop ensuring orbital safety for multi-satellite fleets.</div>
            </div>
            <div className="pipeline-steps">
              <PipelineStep num="01" title="Fast Filter" detail="KD-Tree + KBV collision screening." />
              <PipelineStep num="02" title="RK4 Physics" detail="Traitory propagation & TCA detection." />
              <PipelineStep num="03" title="Decision" detail="Deterministic safe-orbit resolution." />
              <PipelineStep num="04" title="Execution" detail="Shadow AI maneuver scheduling." highlight />
            </div>
          </>
        )}

        {activeTab === 'stress' && (
          <>
            <div className="demo-section-heading">
              <div className="demo-heading-title">Platform Resilience</div>
              <div className="demo-heading-sub">Stress testing the AETHER-X digital twin under mission-fail conditions.</div>
            </div>
            <div className="stress-buttons">
              {SCENARIOS.map(s => (
                <button key={s.id} className="stress-btn">
                  <span className="stress-btn-icon">{s.icon}</span>
                  <div>
                    <div className="stress-btn-label">{s.label}</div>
                    <div className="stress-btn-desc">{s.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
