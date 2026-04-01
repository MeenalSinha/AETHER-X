import React, { useEffect, useRef, useState, useCallback } from 'react'
import './GroundTrackMap.css'

const W = 1200, H = 560

function mercatorX(lon) { return ((lon + 180) / 360) * W }
function mercatorY(lat) {
  const r = Math.min(Math.max(lat, -85), 85)
  const s = Math.sin((r * Math.PI) / 180)
  return (H / 2) - (W / (2 * Math.PI)) * Math.log((1 + s) / (1 - s)) / 2
}

const RISK_COLOR = {
  NOMINAL:  '#16a34a',
  ADVISORY: '#2563eb',
  WARNING:  '#d97706',
  CRITICAL: '#dc2626',
  EOL:      '#7c3aed',
}

export default function GroundTrackMap({ snapshot, selectedSat, onSelectSat }) {
  const canvasRef  = useRef(null)
  const bgRef      = useRef(null)   // offscreen canvas for static world map
  const [tooltip, setTooltip] = useState(null)

  // Draw static world map once
  useEffect(() => {
    const bg = document.createElement('canvas')
    bg.width = W; bg.height = H
    const ctx = bg.getContext('2d')
    // Ocean
    ctx.fillStyle = '#e8edf5'
    ctx.fillRect(0, 0, W, H)
    // Graticule
    ctx.strokeStyle = '#d0d8e8'
    ctx.lineWidth = 0.4
    for (let lon = -180; lon <= 180; lon += 30) {
      ctx.beginPath()
      ctx.moveTo(mercatorX(lon), 0)
      ctx.lineTo(mercatorX(lon), H)
      ctx.stroke()
    }
    for (let lat = -60; lat <= 60; lat += 30) {
      ctx.beginPath()
      ctx.moveTo(0, mercatorY(lat))
      ctx.lineTo(W, mercatorY(lat))
      ctx.stroke()
    }
    // Equator
    ctx.strokeStyle = '#b0bcd0'
    ctx.lineWidth = 0.8
    ctx.beginPath(); ctx.moveTo(0, mercatorY(0)); ctx.lineTo(W, mercatorY(0)); ctx.stroke()
    bgRef.current = bg
  }, [])

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || !bgRef.current) return
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, W, H)

    // Blit static background
    ctx.drawImage(bgRef.current, 0, 0)

    if (!snapshot) return

    // Terminator line
    if (snapshot.terminator?.length) {
      ctx.beginPath()
      ctx.strokeStyle = 'rgba(100,120,160,0.35)'
      ctx.lineWidth = 1.5
      ctx.setLineDash([4, 4])
      snapshot.terminator.forEach(([lon, lat], i) => {
        const x = mercatorX(lon), y = mercatorY(lat)
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      })
      ctx.stroke()
      ctx.setLineDash([])
    }

    // Debris cloud
    ctx.fillStyle = 'rgba(100,116,139,0.25)'
    for (const [, lat, lon] of (snapshot.debris_cloud || [])) {
      const x = mercatorX(lon), y = mercatorY(lat)
      ctx.beginPath()
      ctx.arc(x, y, 1.2, 0, Math.PI * 2)
      ctx.fill()
    }

    // Satellites
    const sats = snapshot.satellites || []
    for (const sat of sats) {
      const x = mercatorX(sat.lon), y = mercatorY(sat.lat)
      const isSelected = sat.id === selectedSat
      const color = RISK_COLOR[sat.risk] || RISK_COLOR.NOMINAL

      // History trail
      if (sat.history?.length > 1) {
        ctx.beginPath()
        ctx.strokeStyle = `${color}55`
        ctx.lineWidth = 1
        let first = true
        let prevLon = null
        for (const [hlat, hlon] of sat.history) {
          const hx = mercatorX(hlon), hy = mercatorY(hlat)
          if (prevLon !== null && Math.abs(hlon - prevLon) > 180) {
            ctx.stroke()
            ctx.beginPath()
            first = true
          }
          first ? ctx.moveTo(hx, hy) : ctx.lineTo(hx, hy)
          first = false
          prevLon = hlon
        }
        ctx.stroke()
      }

      // Satellite dot
      const r = isSelected ? 6 : 4
      ctx.beginPath()
      ctx.arc(x, y, r, 0, Math.PI * 2)
      ctx.fillStyle = '#fff'
      ctx.fill()
      ctx.strokeStyle = color
      ctx.lineWidth = isSelected ? 2.5 : 1.5
      ctx.stroke()

      if (isSelected) {
        // Selection ring
        ctx.beginPath()
        ctx.arc(x, y, 10, 0, Math.PI * 2)
        ctx.strokeStyle = `${color}66`
        ctx.lineWidth = 1
        ctx.stroke()

        // ID label
        ctx.font = '600 10px DM Sans, sans-serif'
        ctx.fillStyle = color
        ctx.fillText(sat.id, x + 8, y - 4)
      }

      // Pending burn indicator
      if (sat.pending_burns?.length > 0) {
        ctx.beginPath()
        ctx.arc(x, y, r + 3, 0, Math.PI * 2)
        ctx.strokeStyle = '#d97706'
        ctx.lineWidth = 1
        ctx.setLineDash([2, 2])
        ctx.stroke()
        ctx.setLineDash([])
      }
    }
  }, [snapshot, selectedSat])

  useEffect(() => { draw() }, [draw])

  const handleClick = useCallback((e) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const scaleX = W / rect.width
    const scaleY = H / rect.height
    const cx = (e.clientX - rect.left) * scaleX
    const cy = (e.clientY - rect.top)  * scaleY

    const sats = snapshot?.satellites || []
    for (const sat of sats) {
      const x = mercatorX(sat.lon), y = mercatorY(sat.lat)
      if (Math.hypot(cx - x, cy - y) < 12) {
        onSelectSat(sat.id === selectedSat ? null : sat.id)
        return
      }
    }
    onSelectSat(null)
  }, [snapshot, selectedSat, onSelectSat])

  const handleMouseMove = useCallback((e) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const scaleX = W / rect.width
    const scaleY = H / rect.height
    const cx = (e.clientX - rect.left) * scaleX
    const cy = (e.clientY - rect.top)  * scaleY

    const sats = snapshot?.satellites || []
    for (const sat of sats) {
      const x = mercatorX(sat.lon), y = mercatorY(sat.lat)
      if (Math.hypot(cx - x, cy - y) < 10) {
        setTooltip({ sat, px: e.clientX, py: e.clientY })
        return
      }
    }
    setTooltip(null)
  }, [snapshot])

  return (
    <div className="groundtrack-wrap">
      <div className="panel-header">
        Ground Track Map
        <span className="text-muted mono" style={{ fontSize: 10 }}>
          {snapshot?.satellites?.length ?? 0} active / {snapshot?.debris_cloud?.length?.toLocaleString() ?? 0} debris
        </span>
      </div>

      <div className="map-legend">
        {Object.entries(RISK_COLOR).map(([k, c]) => (
          <span key={k} className="legend-item">
            <span className="legend-dot" style={{ background: c }} />
            {k}
          </span>
        ))}
        <span className="legend-item">
          <span className="legend-dot" style={{ background: 'rgba(100,116,139,0.5)' }} />
          DEBRIS
        </span>
      </div>

      <div className="canvas-wrap">
        <canvas
          ref={canvasRef}
          width={W} height={H}
          className="world-canvas"
          onClick={handleClick}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setTooltip(null)}
        />
      </div>

      {tooltip && (
        <div className="map-tooltip" style={{ left: tooltip.px + 12, top: tooltip.py - 10 }}>
          <strong className="mono">{tooltip.sat.id}</strong>
          <div>{tooltip.sat.lat.toFixed(2)}, {tooltip.sat.lon.toFixed(2)}</div>
          <div>Alt: {tooltip.sat.alt_km?.toFixed(1)} km</div>
          <div>Fuel: {(tooltip.sat.fuel_fraction * 100).toFixed(1)}%</div>
          <div>Status: <span style={{ color: RISK_COLOR[tooltip.sat.risk] }}>{tooltip.sat.risk}</span></div>
        </div>
      )}
    </div>
  )
}
