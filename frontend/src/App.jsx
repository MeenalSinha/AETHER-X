import React, { useState } from 'react'
import { useSimulation } from './hooks/useSimulation'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import GroundTrackMap from './components/GroundTrackMap'
import BullseyePlot from './components/BullseyePlot'
import FleetHealthPanel from './components/FleetHealthPanel'
import ManeuverTimeline from './components/ManeuverTimeline'
import ConjunctionTable from './components/ConjunctionTable'
import PerformanceLog from './components/PerformanceLog'
import DemoPanel from './components/DemoPanel'
import './App.css'

export default function App() {
  const sim = useSimulation(3000)
  const [selectedSat, setSelectedSat] = useState(null)
  const [activeView, setActiveView] = useState('map')  // map | fleet | timeline | conjunctions | perf

  return (
    <div className="app-shell">
      <Header
        connected={sim.connected}
        status={sim.status}
        stepping={sim.stepping}
        lastStep={sim.lastStep}
        onStep={sim.runStep}
        onRefresh={sim.refresh}
      />

      <div className="app-body">
        <Sidebar
          activeView={activeView}
          setActiveView={setActiveView}
          status={sim.status}
          conjunctions={sim.conjunctions}
        />

        <main className="app-main">
          {activeView === 'map' && (
            <div className="view-map">
              <div className="map-container panel">
                <GroundTrackMap
                  snapshot={sim.snapshot}
                  selectedSat={selectedSat}
                  onSelectSat={setSelectedSat}
                />
              </div>
              <div className="map-side">
                <BullseyePlot
                  conjunctions={sim.conjunctions}
                  selectedSat={selectedSat}
                  snapshot={sim.snapshot}
                />
                <ConjunctionTable
                  conjunctions={sim.conjunctions.slice(0, 8)}
                  onSelect={id => setSelectedSat(id)}
                  selectedSat={selectedSat}
                />
              </div>
            </div>
          )}

          {activeView === 'fleet' && (
            <FleetHealthPanel
              fleetHealth={sim.fleetHealth}
              snapshot={sim.snapshot}
              onSelect={setSelectedSat}
              selectedSat={selectedSat}
            />
          )}

          {activeView === 'timeline' && (
            <ManeuverTimeline
              maneuverLog={sim.maneuverLog}
              snapshot={sim.snapshot}
              status={sim.status}
            />
          )}

          {activeView === 'conjunctions' && (
            <ConjunctionTable
              conjunctions={sim.conjunctions}
              onSelect={id => setSelectedSat(id)}
              selectedSat={selectedSat}
              full
            />
          )}

          {activeView === 'perf' && (
            <PerformanceLog performance={sim.performance} />
          )}

          {activeView === 'demo' && (
            <DemoPanel 
              conjunctions={sim.conjunctions} 
              onStep={sim.refresh} 
              onStress={sim.refresh}
            />
          )}
        </main>
      </div>
    </div>
  )
}
