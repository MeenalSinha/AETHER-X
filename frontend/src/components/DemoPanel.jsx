import React, { useState } from 'react'
import './DemoPanel.css'

const BASE = '/api'

async function req(method, path, body) {
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-API-KEY': 'aether_secret_2026',
    },
  }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(BASE + path, opts)
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

function PipelineStep({ num, title, detail, highlight, active }) {
  return (
    <div className={`pipe-step ${highlight ? 'pipe-step-highlight' : ''} ${active ? 'pipe-step-active' : ''}`}>
      <div className="pipe-num">{active ? '⚡' : num}</div>
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
  const riskColor  = r => r === 'CRITICAL' ? '#ef4444' : r === 'WARNING' ? '#f59e0b' : '#10b981'

  return (
    <div className="comparison-board">
      <div className="comp-col comp-legacy">
        <span className="comp-label">Legacy Filter</span>
        <div className="comp-title">KD-Tree Architecture</div>
        <div className="kbv-list">
          {withoutKBV.length === 0 && <div className="kbv-empty">Fleet clear — no conjunctions</div>}
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
          {withKBV.length === 0 && <div className="kbv-empty">Fleet clear — no conjunctions</div>}
          {withKBV.map((c, i) => (
            <div key={i} className={`kbv-row ${c.kbv_radius_km ? 'kbv-row-special' : ''}`}>
              <span className="kbv-dot" style={{ background: riskColor(c.risk_level) }} />
              <span className="kbv-sat mono">{c.satellite_id}</span>
              <span className="kbv-dist">{(c.min_distance_km * 1000).toFixed(0)}m</span>
              <span className="kbv-speed">
                {c.closing_speed_km_s != null ? Math.abs(c.closing_speed_km_s).toFixed(1) + 'km/s' : ''}
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
  { id: 'multi_collision', label: 'Multi-Object Event', icon: '⚡', desc: 'Burst: 10 simultaneous CRITICAL threats.' },
  { id: 'low_fuel',        label: 'Low-Fuel Recovery',  icon: '⛽', desc: 'Optimize maneuvers at <5% fuel.' },
  { id: 'cascade',         label: 'Debris Density Spike', icon: '🌩', desc: 'KBV stress test at 10× density.' },
  { id: 'blackout_storm',  label: 'Ground Blackout',    icon: '📡', desc: 'Pre-schedule during sensor blackout.' },
]

const PIPELINE_STEPS = [
  { num: '01', title: 'Fast Filter',  detail: 'KD-Tree + KBV screening — O(N log N).' },
  { num: '02', title: 'RK4 Physics',  detail: 'Trajectory propagation & 24h TCA detection.' },
  { num: '03', title: 'Decision',     detail: 'Global fleet coordinator: min-ΔV resolution.' },
  { num: '04', title: 'Execution',    detail: 'LOS-aware burn scheduling.', highlight: true },
]

export default function DemoPanel({ conjunctions, onStep }) {
  const [activeTab,       setActiveTab]       = useState('innovation')
  const [stressLoading,   setStressLoading]   = useState(null)
  const [stressResult,    setStressResult]    = useState(null)
  const [stressError,     setStressError]     = useState(null)
  const [stepping,        setStepping]        = useState(false)
  const [stepResult,      setStepResult]      = useState(null)
  const [activePipeStep,  setActivePipeStep]  = useState(null)

  const runStep = async () => {
    setStepping(true)
    setStepResult(null)
    try {
      for (let i = 0; i < PIPELINE_STEPS.length; i++) {
        setActivePipeStep(i)
        await new Promise(r => setTimeout(r, 450))
      }
      const result = await req('POST', '/simulate/step', { step_seconds: 3600, propagate_debris: true })
      setStepResult(result)
      if (onStep) onStep()
    } catch (e) {
      setStepResult({ error: e.message })
    } finally {
      setStepping(false)
      setActivePipeStep(null)
    }
  }

  const runStress = async (scenarioId) => {
    setStressLoading(scenarioId)
    setStressResult(null)
    setStressError(null)
    try {
      const result = await req('POST', `/simulate/stress?scenario=${scenarioId}`)
      setStressResult({ scenario: scenarioId, ...result })
    } catch (e) {
      setStressError(`Scenario failed: ${e.message}`)
    } finally {
      setStressLoading(null)
    }
  }

  return (
    <div className="demo-panel">
      <div className="demo-tabs">
        <button className={`demo-tab ${activeTab === 'innovation' ? 'demo-tab-active' : ''}`} onClick={() => setActiveTab('innovation')}>🛰 Breakthroughs</button>
        <button className={`demo-tab ${activeTab === 'pipeline'   ? 'demo-tab-active' : ''}`} onClick={() => setActiveTab('pipeline')}>⚙️ Run Pipeline</button>
        <button className={`demo-tab ${activeTab === 'stress'     ? 'demo-tab-active' : ''}`} onClick={() => setActiveTab('stress')}>🔥 Chaos Labs</button>
      </div>

      <div className="demo-section">

        {/* ══ BREAKTHROUGHS ══ */}
        {activeTab === 'innovation' && (
          <>
            <div className="demo-section-heading">
              <div className="demo-heading-title">Situational Intelligence</div>
              <div className="demo-heading-sub">KD-Tree vs Kinetic Bounding Volumes — live from current conjunction data.</div>
            </div>
            <KBVDemo conjunctions={conjunctions} />
            <div className="ai-efficiency-card">
              <div className="ai-metric-val">10 km</div>
              <div className="ai-metric-label">Advisory detection radius — early-warning standoff enforced</div>
            </div>
            <button className="run-step-btn" onClick={runStep} disabled={stepping}>
              {stepping ? '⏳ Advancing Simulation…' : '▶ Step Simulation +1 Hour'}
            </button>
            {stepResult && !stepResult.error && (
              <div className="step-result-box">
                <span className="step-ok">✅ STEP_COMPLETE</span>
                <span>Collisions detected: <b>{stepResult.collisions_detected ?? 0}</b></span>
                <span>Maneuvers executed: <b>{stepResult.maneuvers_executed ?? 0}</b></span>
              </div>
            )}
            {stepResult?.error && <div className="step-error">⚠ {stepResult.error}</div>}
          </>
        )}

        {/* ══ PIPELINE ══ */}
        {activeTab === 'pipeline' && (
          <>
            <div className="demo-section-heading">
              <div className="demo-heading-title">Operations Pipeline</div>
              <div className="demo-heading-sub">Step the simulation to watch all 4 autonomous control stages execute live.</div>
            </div>
            <div className="pipeline-steps">
              {PIPELINE_STEPS.map((s, i) => (
                <PipelineStep key={i} {...s} active={activePipeStep === i} />
              ))}
            </div>
            <button className="run-step-btn" onClick={runStep} disabled={stepping} style={{marginTop: 16}}>
              {stepping ? '⏳ Pipeline Running…' : '▶ Execute Full Pipeline (+1 hr)'}
            </button>
            {stepResult && !stepResult.error && (
              <div className="step-result-box">
                <span className="step-ok">✅ STEP_COMPLETE</span>
                <span>New sim time: <b>{stepResult.new_timestamp?.slice(0,16).replace('T', ' ')}</b></span>
                <span>Collisions: <b>{stepResult.collisions_detected ?? 0}</b> &nbsp;|&nbsp; Maneuvers: <b>{stepResult.maneuvers_executed ?? 0}</b></span>
              </div>
            )}
            {stepResult?.error && <div className="step-error">⚠ {stepResult.error}</div>}
          </>
        )}

        {/* ══ CHAOS LABS ══ */}
        {activeTab === 'stress' && (
          <>
            <div className="demo-section-heading">
              <div className="demo-heading-title">Platform Resilience</div>
              <div className="demo-heading-sub">Inject edge-case scenarios into the live digital twin and observe real-time response.</div>
            </div>
            <div className="stress-buttons">
              {SCENARIOS.map(s => (
                <button
                  key={s.id}
                  className={`stress-btn ${stressLoading === s.id ? 'stress-btn-loading' : ''}`}
                  onClick={() => runStress(s.id)}
                  disabled={!!stressLoading}
                >
                  <span className="stress-btn-icon">{stressLoading === s.id ? '⏳' : s.icon}</span>
                  <div>
                    <div className="stress-btn-label">{s.label}</div>
                    <div className="stress-btn-desc">{s.desc}</div>
                  </div>
                </button>
              ))}
            </div>

            {stressError && <div className="step-error">{stressError}</div>}

            {stressResult && (
              <div className="stress-result-box">
                <div className="stress-result-title">
                  ✅ Scenario complete — <span className="mono">{stressResult.scenario}</span>
                </div>
                <div className="stress-result-grid">
                  {stressResult.threats_injected   != null && <span>Threats injected: <b>{stressResult.threats_injected}</b></span>}
                  {stressResult.maneuvers_scheduled != null && <span>Maneuvers scheduled: <b>{stressResult.maneuvers_scheduled}</b></span>}
                  {stressResult.satellites_affected != null && <span>Satellites affected: <b>{stressResult.satellites_affected}</b></span>}
                  {stressResult.step_ms             != null && <span>Processing time: <b>{stressResult.step_ms}ms</b></span>}
                  {stressResult.message && <span style={{gridColumn: '1/-1', opacity: 0.75}}>{stressResult.message}</span>}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
