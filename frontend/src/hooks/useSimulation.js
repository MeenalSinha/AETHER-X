import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../services/api'

export function useSimulation(pollMs = 3000) {
  const [snapshot, setSnapshot]         = useState(null)
  const [status, setStatus]             = useState(null)
  const [conjunctions, setConjunctions] = useState([])
  const [fleetHealth, setFleetHealth]   = useState([])
  const [maneuverLog, setManeuverLog]   = useState([])
  const [performance, setPerformance]   = useState([])
  const [connected, setConnected]       = useState(false)
  const [stepping, setStepping]         = useState(false)
  const [lastStep, setLastStep]         = useState(null)
  const pollRef = useRef(null)

  const fetchAll = useCallback(async () => {
    try {
      const [snap, stat, conj, fleet, perf] = await Promise.all([
        api.getSnapshot(),
        api.getStatus(),
        api.getConjunctions(30),
        api.getFleetHealth(),
        api.getPerformance(20),
      ])
      setSnapshot(snap)
      setStatus(stat)
      setConjunctions(conj.warnings || [])
      setFleetHealth(fleet.fleet || [])
      setPerformance(perf.log || [])
      setConnected(true)
    } catch (e) {
      setConnected(false)
    }
  }, [])

  const fetchLog = useCallback(async () => {
    try {
      const log = await api.getManeuverLog(50)
      setManeuverLog(log.log || [])
    } catch {}
  }, [])

  useEffect(() => {
    fetchAll()
    fetchLog()
    pollRef.current = setInterval(() => {
      fetchAll()
    }, pollMs)
    return () => clearInterval(pollRef.current)
  }, [fetchAll, pollMs])

  const runStep = useCallback(async (seconds = 3600) => {
    setStepping(true)
    try {
      const result = await api.step(seconds)
      setLastStep(result)
      await fetchAll()
      await fetchLog()
    } catch (e) {
      console.error('Step failed', e)
    } finally {
      setStepping(false)
    }
  }, [fetchAll, fetchLog])

  const refresh = useCallback(() => {
    fetchAll()
    fetchLog()
  }, [fetchAll, fetchLog])

  return {
    snapshot, status, conjunctions, fleetHealth,
    maneuverLog, performance, connected,
    stepping, lastStep,
    runStep, refresh,
  }
}
