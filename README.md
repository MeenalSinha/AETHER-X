# AETHER-X: Autonomous Constellation Manager

**National Space Hackathon 2026 — IIT Delhi**  
Orbital Debris Avoidance & Constellation Management System

---

## Architecture Overview

```
aether-x/
├── backend/                   # Python + FastAPI physics engine
│   ├── main.py                # App entry point, CORS, lifespan
│   ├── api/
│   │   ├── telemetry.py       # POST /api/telemetry
│   │   ├── maneuver.py        # POST /api/maneuver/schedule
│   │   ├── simulate.py        # POST /api/simulate/step
│   │   └── visualization.py  # GET  /api/visualization/snapshot
│   ├── core/
│   │   └── simulation_state.py  # Singleton sim state, constants, ECI math
│   ├── engine/
│   │   ├── physics.py         # RK4+J2 propagation, KD-Tree + KBV, TCA, RTN
│   │   └── optimizer.py       # Global Fleet Coordinator (MILP-lite), AI-Ready
│   └── utils/
│       └── static.py          # Frontend SPA static serving
│
├── frontend/                  # React + Canvas + Recharts dashboard
│   ├── src/
│   │   ├── App.jsx            # Root layout, view router
│   │   ├── index.css          # Design system (light theme, CSS vars)
│   │   ├── components/
│   │   │   ├── Header.jsx         # Sim controls, status chips
│   │   │   ├── Sidebar.jsx        # Navigation, fleet summary
│   │   │   ├── GroundTrackMap.jsx # Mercator canvas: sats + debris + terminator
│   │   │   ├── BullseyePlot.jsx   # Polar conjunction chart
│   │   │   ├── FleetHealthPanel.jsx # Fuel gauges, scatter/histogram
│   │   │   ├── ManeuverTimeline.jsx # Gantt: burns + cooldowns
│   │   │   ├── ConjunctionTable.jsx # Sortable CDM warnings table
│   │   │   └── PerformanceLog.jsx  # Timing charts + raw log table
│   │   ├── hooks/
│   │   │   └── useSimulation.js   # Central polling hook (3s interval)
│   │   └── services/
│   │       └── api.js             # Typed API client
│   ├── vite.config.js
│   └── package.json
│
├── infra/
│   └── start.sh               # Container startup script
├── Dockerfile                 # ubuntu:22.04, port 8000
└── docker-compose.yml
```

---

## Quick Start

### Option A: Docker (Production)
```bash
docker build -t aether-x .
docker run -p 8000:8000 aether-x
```
Then open: http://localhost:8000

### Option B: Docker Compose
```bash
docker compose up --build
```

### Option C: Local Development

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend (separate terminal):**
```bash
cd frontend
npm install
npm run dev          # http://localhost:3000 — proxies /api → :8000
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/telemetry` | Ingest ECI state vectors |
| `POST` | `/api/maneuver/schedule` | Schedule burn sequence |
| `POST` | `/api/simulate/step` | Advance simulation |
| `GET`  | `/api/simulate/status` | Fleet summary |
| `GET`  | `/api/simulate/conjunctions` | Active CDM warnings |
| `GET`  | `/api/simulate/performance` | Engine timing log |
| `GET`  | `/api/visualization/snapshot` | Full frontend snapshot |
| `GET`  | `/api/visualization/fleet/health` | Per-satellite health |
| `GET`  | `/api/visualization/satellite/{id}/trajectory` | Predicted path |
| `GET`  | `/health` | Liveness check |
| `GET`  | `/docs` | Swagger UI |

---

## Physics & Algorithms

### Orbital Propagation
- **Integrator:** 4th-order Runge-Kutta (RK4)
- **Perturbations:** J2 gravitational harmonic (equatorial bulge)
- **Frame:** Earth-Centered Inertial (ECI, J2000)
- **Constants:** μ = 398600.4418 km³/s², RE = 6378.137 km, J2 = 1.08263×10⁻³

### Collision Detection
- **Threshold:** 100 m (0.100 km)
- **Spatial index:** KD-Tree (scipy) — O(N log N) vs naïve O(N²)
- **TCA search:** 24-hour horizon with 30s step + early exit
- **Pre-filter:** 200 km radius query per satellite

### Maneuver Planning (RTN Frame)
- Evasion: prograde/retrograde transverse burns (fuel-optimal)
- Recovery: phasing burn toward nominal orbital slot
- Fuel: Tsiolkovsky rocket equation with dynamic mass tracking
- Cooldown: 600 s enforced between burns
- LOS check: geometric elevation mask against 6 ground stations
- EOL trigger: ≤5% fuel → graveyard orbit maneuver

### Global Fleet Coordination (AI-Ready)
1. **Safety:** Global collision priority ranking (primary)
2. **Fuel:** Multi-satellite ΔV minimization (MILP-lite heuristics)
3. **Uptime:** Deterministic baseline for RL training supervisor
4. **AI-Ready:** Interface 1:1 compatible with PPO/SAC agents

---

## Evaluation Targets

| Criterion | Implementation |
|-----------|---------------|
| Safety (25%) | KD-Tree CDM pipeline, auto-scheduled evasions |
| Fuel Efficiency (20%) | Transverse burns, Tsiolkovsky tracking |
| Uptime (15%) | Recovery burns, station-keeping monitor |
| Algo Speed (15%) | KD-Tree O(N log N), benchmarked per step |
| UI/UX (15%) | Canvas ground track, bullseye, Gantt, charts |
| Code Quality (10%) | Modular, typed, logged |

---

## Ground Stations

| ID | Name | Lat | Lon | Min El |
|----|------|-----|-----|--------|
| GS-001 | ISTRAC Bengaluru | 13.03 | 77.52 | 5° |
| GS-002 | Svalbard | 78.23 | 15.41 | 5° |
| GS-003 | Goldstone | 35.43 | -116.89 | 10° |
| GS-004 | Punta Arenas | -53.15 | -70.92 | 5° |
| GS-005 | IIT Delhi | 28.55 | 77.19 | 15° |
| GS-006 | McMurdo | -77.85 | 166.67 | 5° |

---

## Spacecraft Constants

| Parameter | Value |
|-----------|-------|
| Dry mass | 500 kg |
| Initial fuel | 50 kg |
| Isp | 300 s |
| Max ΔV/burn | 15 m/s |
| Thruster cooldown | 600 s |
| EOL fuel threshold | 5% |
| Collision threshold | 100 m |
| Station-keeping radius | 10 km |
| Comm latency | 10 s |
