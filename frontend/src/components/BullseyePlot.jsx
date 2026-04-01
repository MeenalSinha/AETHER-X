import React, { useRef, useEffect } from 'react'
import './BullseyePlot.css'

const SIZE = 260
const CX   = SIZE / 2
const CY   = SIZE / 2
const R_MAX = 100

function riskColor(km) {
  if (km < 0.1)  return '#ef4444' // Red
  if (km < 1.0)  return '#f59e0b' // Amber
  if (km < 5.0)  return '#0d9488' // Teal
  return '#10b981' // Green
}

export default function BullseyePlot({ conjunctions, selectedSat }) {
  const canvasRef = useRef(null)
  const angleRef = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let frame

    const draw = () => {
      ctx.clearRect(0, 0, SIZE, SIZE)

      // Light Pro Tactical Backdrop
      ctx.beginPath()
      ctx.arc(CX, CY, R_MAX + 10, 0, Math.PI * 2)
      ctx.fillStyle = '#f9fafb'
      ctx.fill()
      ctx.strokeStyle = '#e5e7eb'
      ctx.lineWidth = 1
      ctx.stroke()

      // Rings
      const rings = [0.1, 1, 5, 20]
      const ringLabels = ['0.1km', '1km', '5km', '20km']
      rings.forEach((r, i) => {
        const cr = (i + 1) * (R_MAX / rings.length)
        ctx.beginPath()
        ctx.arc(CX, CY, cr, 0, Math.PI * 2)
        ctx.strokeStyle = i === 0 ? 'rgba(239, 68, 68, 0.2)' : '#e5e7eb'
        ctx.setLineDash(i === 0 ? [] : [3, 4])
        ctx.lineWidth = 1
        ctx.stroke()
        ctx.setLineDash([])

        // Label
        ctx.font = '700 8px JetBrains Mono, monospace'
        ctx.fillStyle = '#9ca3af'
        ctx.fillText(ringLabels[i], CX + cr + 4, CY - 2)
      })

      // Crosshairs
      ctx.strokeStyle = '#f1f5f9'
      ctx.lineWidth = 1
      ctx.beginPath(); ctx.moveTo(CX, CY - R_MAX - 10); ctx.lineTo(CX, CY + R_MAX + 10); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(CX - R_MAX - 10, CY); ctx.lineTo(CX + R_MAX + 10, CY); ctx.stroke()

      // Scan-Sweep Animation (Light Mode)
      angleRef.current = (angleRef.current + 0.015) % (Math.PI * 2)
      
      const sweepGrad = ctx.createRadialGradient(CX, CY, 0, CX, CY, R_MAX + 10)
      sweepGrad.addColorStop(0, 'rgba(37, 99, 235, 0)')
      sweepGrad.addColorStop(1, 'rgba(37, 99, 235, 0.06)')

      ctx.beginPath()
      ctx.moveTo(CX, CY)
      ctx.arc(CX, CY, R_MAX + 10, angleRef.current - 0.3, angleRef.current, false)
      ctx.closePath()
      ctx.fillStyle = sweepGrad
      ctx.fill()

      // Center (selected sat) - Blue Dot
      ctx.save()
      ctx.shadowBlur = 4
      ctx.shadowColor = 'rgba(37, 99, 235, 0.3)'
      ctx.beginPath()
      ctx.arc(CX, CY, 6, 0, Math.PI * 2)
      ctx.fillStyle = '#2563eb'
      ctx.fill()
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2
      ctx.stroke()
      ctx.restore()

      // Debris
      const satConj = selectedSat
        ? conjunctions.filter(c => c.satellite_id === selectedSat)
        : conjunctions.slice(0, 15)

      satConj.forEach(c => {
        const dist = Math.min(c.min_distance_km, 20)
        const r_scaled = (dist / 20) * R_MAX
        const id_num = parseInt(c.debris_id.replace(/\D/g, '') || '0')
        const angle = (id_num % 360) * (Math.PI / 180)
        
        const dx = CX + r_scaled * Math.cos(angle)
        const dy = CY + r_scaled * Math.sin(angle)

        ctx.save()
        ctx.shadowBlur = 4
        ctx.shadowColor = 'rgba(0,0,0,0.1)'
        ctx.beginPath()
        ctx.arc(dx, dy, 5, 0, Math.PI * 2)
        ctx.fillStyle = riskColor(c.min_distance_km)
        ctx.fill()
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 1.5
        ctx.stroke()
        ctx.restore()
      })

      frame = requestAnimationFrame(draw)
    }

    draw()
    return () => cancelAnimationFrame(frame)
  }, [conjunctions, selectedSat])

  const displayedCount = selectedSat
    ? conjunctions.filter(c => c.satellite_id === selectedSat).length
    : Math.min(conjunctions.length, 15)

  return (
    <div className="bullseye-panel panel">
      <div className="panel-header">
        <span>Situational Radar</span>
        <span className="badge badge-blue">{selectedSat ? selectedSat : 'Fleet Global'}</span>
      </div>
      <div className="bullseye-body">
        <canvas ref={canvasRef} width={SIZE} height={SIZE} className="bullseye-canvas" />
        <div className="bullseye-legend">
          <div className="bl-title">Proximity Legend</div>
          <div className="bl-row"><span className="bl-dot" style={{background:'#ef4444'}} /><span>CRITICAL</span></div>
          <div className="bl-row"><span className="bl-dot" style={{background:'#f59e0b'}} /><span>WARNING</span></div>
          <div className="bl-row"><span className="bl-dot" style={{background:'#0d9488'}} /><span>ADVISORY</span></div>
          <div className="bl-row"><span className="bl-dot" style={{background:'#10b981'}} /><span>NOMINAL</span></div>
          <div className="bl-meta mono mt-auto">{displayedCount} contacts</div>
        </div>
      </div>
    </div>
  )
}
