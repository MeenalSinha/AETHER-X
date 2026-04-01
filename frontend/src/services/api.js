const BASE = '/api'

async function req(method, path, body) {
  const opts = {
    method,
    headers: { 
      'Content-Type': 'application/json',
      'X-API-KEY': 'aether_secret_2026' // Matches MASTER_API_KEY in main.py
    },
  }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(BASE + path, opts)
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`${res.status}: ${err}`)
  }
  return res.json()
}

export const api = {
  // Telemetry
  ingestTelemetry: (payload)      => req('POST', '/telemetry', payload),

  // Maneuvers
  scheduleManeuver: (payload)     => req('POST', '/maneuver/schedule', payload),
  getManeuverLog: (limit = 100)   => req('GET',  `/maneuver/log?limit=${limit}`),

  // Simulation
  step: (step_seconds)            => req('POST', '/simulate/step', { step_seconds }),
  getStatus: ()                   => req('GET',  '/simulate/status'),
  getConjunctions: (limit = 50)   => req('GET',  `/simulate/conjunctions?limit=${limit}`),
  getPerformance: (limit = 20)    => req('GET',  `/simulate/performance?limit=${limit}`),
  getScalability: ()               => req('GET',  '/simulate/scalability'),
  runStress: (scenario)            => req('POST', `/simulate/stress?scenario=${scenario}`),

  // Visualization
  getSnapshot: ()                 => req('GET',  '/visualization/snapshot'),
  getTrajectory: (id, mins = 90)  => req('GET',  `/visualization/satellite/${id}/trajectory?horizon_minutes=${mins}`),
  getFleetHealth: ()              => req('GET',  '/visualization/fleet/health'),

  // Health check
  health: ()                      => req('GET',  '/health').catch(() =>
    fetch('/health').then(r => r.json())
  ),
}
