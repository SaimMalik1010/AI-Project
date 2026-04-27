import { useEffect, useMemo, useState } from 'react'

import { createWarehouseMap, getOptimalRoute } from './apiService.js'
import './WarehouseGrid.css'

const getCellKey = (row, col) => `${row}-${col}`

const createLayout = (aisleCount, shelvesPerAisle) => {
  const rows = aisleCount * 2 + 1
  const cols = shelvesPerAisle + 2
  const layout = Array.from({ length: rows }, () => Array.from({ length: cols }, () => 0))

  for (let aisle = 0; aisle < aisleCount; aisle += 1) {
    const row = aisle * 2 + 1
    for (let col = 1; col <= shelvesPerAisle; col += 1) {
      layout[row][col] = 1
    }
  }

  return layout
}

const createRobotDraft = (suffix, cols = 2) => ({
  id: `R${suffix}`,
  startRow: '0',
  startCol: '0',
  stops: [],
  priority: String(suffix),
})

const getCellClassName = (cellType, hasGoal, hasStop, hasActiveStop, isSelectable) => {
  if (cellType === 1) {
    const shelfClasses = ['cell', 'cell-shelf']
    if (hasStop) shelfClasses.push('cell-stop')
    if (hasActiveStop) shelfClasses.push('cell-active-stop')
    if (isSelectable) shelfClasses.push('cell-selectable')
    return shelfClasses.join(' ')
  }
  if (hasActiveStop) return 'cell cell-active-stop'
  if (hasStop) return 'cell cell-stop'
  if (hasGoal) return 'cell cell-goal'
  if (isSelectable) return 'cell cell-floor cell-selectable'
  return 'cell cell-floor'
}

function WarehouseGrid() {
  const [aisleCountInput, setAisleCountInput] = useState('4')
  const [shelvesPerAisleInput, setShelvesPerAisleInput] = useState('12')
  const [isConfigured, setIsConfigured] = useState(false)
  const [warehouseMapId, setWarehouseMapId] = useState(null)
  const [baseLayout, setBaseLayout] = useState([])
  const [robotDrafts, setRobotDrafts] = useState([createRobotDraft(1), createRobotDraft(2)])
  const [plannedRobots, setPlannedRobots] = useState([])
  const [conflictsResolved, setConflictsResolved] = useState([])
  const [summary, setSummary] = useState('')
  const [makespan, setMakespan] = useState(0)
  const [currentTick, setCurrentTick] = useState(0)
  const [isAnimating, setIsAnimating] = useState(false)
  const [routeComparison, setRouteComparison] = useState({})
  const [loading, setLoading] = useState(false)
  const [comparisonLoading, setComparisonLoading] = useState(false)
  const [notice, setNotice] = useState('Configure aisles and shelves, then set starts and shelf picks by clicking cells.')
  const [error, setError] = useState('')
  const [selectedRobotIndex, setSelectedRobotIndex] = useState(0)
  const [gridClickMode, setGridClickMode] = useState('stop')
  const [routingAlgorithm, setRoutingAlgorithm] = useState('A*')

  const comparisonAlgorithms = ['A*', 'Greedy Best-First Search', 'Floyd-Warshall']

  useEffect(() => {
    if (!plannedRobots.length || !isAnimating) {
      return undefined
    }

    const timerId = window.setInterval(() => {
      setCurrentTick((tick) => {
        if (tick >= makespan) {
          setIsAnimating(false)
          return makespan
        }
        return tick + 1
      })
    }, 420)

    return () => window.clearInterval(timerId)
  }, [plannedRobots, isAnimating, makespan])

  const robotGoals = useMemo(() => {
    const goals = new Set()
    const source = plannedRobots.length ? plannedRobots : []
    source.forEach((robot) => {
      if (Array.isArray(robot.goal) && robot.goal.length === 2) {
        goals.add(getCellKey(robot.goal[0], robot.goal[1]))
      }
    })
    return goals
  }, [plannedRobots])

  const draftStopsByCell = useMemo(() => {
    const stopMap = new Map()

    robotDrafts.forEach((robot, robotIndex) => {
      const stops = Array.isArray(robot.stops) ? robot.stops : []
      stops.forEach((stop, stopIndex) => {
        const key = getCellKey(stop[0], stop[1])
        const existing = stopMap.get(key) || []
        existing.push({ robotIndex, robotId: robot.id || `R${robotIndex + 1}`, stopIndex })
        stopMap.set(key, existing)
      })
    })

    return stopMap
  }, [robotDrafts])

  const activeRobotId = robotDrafts[selectedRobotIndex]?.id || ''

  const isActiveRobotStop = (row, col) => {
    const activeRobot = robotDrafts[selectedRobotIndex]
    if (!activeRobot || !Array.isArray(activeRobot.stops)) {
      return false
    }
    return activeRobot.stops.some((stop) => stop[0] === row && stop[1] === col)
  }

  const toggleStopForRobot = (robotIndex, row, col) => {
    setRobotDrafts((current) =>
      current.map((robot, index) => {
        if (index !== robotIndex) {
          return robot
        }

        const currentStops = Array.isArray(robot.stops) ? robot.stops : []
        const exists = currentStops.some((stop) => stop[0] === row && stop[1] === col)
        if (exists) {
          return {
            ...robot,
            stops: currentStops.filter((stop) => !(stop[0] === row && stop[1] === col)),
          }
        }

        return {
          ...robot,
          stops: [...currentStops, [row, col]],
        }
      }),
    )
  }

  const setStartForRobot = (robotIndex, row, col) => {
    setRobotDrafts((current) =>
      current.map((robot, index) =>
        index === robotIndex
          ? {
              ...robot,
              startRow: String(row),
              startCol: String(col),
            }
          : robot,
      ),
    )
  }

  const onGridCellClick = (row, col, cellType) => {
    if (selectedRobotIndex < 0 || selectedRobotIndex >= robotDrafts.length) {
      setError('Select a robot card first.')
      return
    }

    if (gridClickMode === 'start') {
      if (cellType === 1) {
        setError('Start position must be on floor, not on a shelf.')
        return
      }
      setError('')
      setStartForRobot(selectedRobotIndex, row, col)
      return
    }

    if (cellType !== 1) {
      setError('Stop selection mode only accepts shelf cells. Click a shelf to add/remove a stop.')
      return
    }

    setError('')
    toggleStopForRobot(selectedRobotIndex, row, col)
  }

  const robotPositionsByCell = useMemo(() => {
    const positionMap = new Map()

    plannedRobots.forEach((robot) => {
      const path = Array.isArray(robot.path) ? robot.path : []
      if (!path.length) {
        return
      }

      const clampedTick = Math.min(currentTick, path.length - 1)
      const cell = path[clampedTick]
      const key = getCellKey(cell[0], cell[1])
      const value = positionMap.get(key) || []
      value.push(robot.id)
      positionMap.set(key, value)
    })

    return positionMap
  }, [plannedRobots, currentTick])

  const robotStateRows = useMemo(() => {
    return plannedRobots.map((robot) => {
      const path = robot.path || []
      if (!path.length) {
        return { id: robot.id, priority: robot.priority, state: 'Idle', flash: false }
      }

      const finished = currentTick >= path.length - 1
      const isWaiting = (robot.wait_times || []).includes(currentTick)
      const yieldedNow = (robot.yield_times || []).includes(currentTick)
      const state = finished ? 'Finished' : isWaiting || yieldedNow ? 'Yielding' : 'Moving'

      return {
        id: robot.id,
        priority: robot.priority,
        state,
        flash: isWaiting || yieldedNow,
      }
    })
  }, [plannedRobots, currentTick])

  const selectedComparisonResult = routeComparison[routingAlgorithm] || null

  const routeComparisonRows = useMemo(() => {
    const rows = comparisonAlgorithms
      .map((algorithm) => {
        const result = routeComparison[algorithm]
        if (!result) {
          return null
        }

        return {
          algorithm,
          distance: result.distance ?? 0,
          pathLength: Array.isArray(result.path) ? result.path.length : 0,
          summary: result.summary || '',
        }
      })
      .filter(Boolean)

    const ranked = [...rows].sort((left, right) => {
      if (left.distance !== right.distance) {
        return left.distance - right.distance
      }
      return left.pathLength - right.pathLength
    })

    const bestAlgorithm = ranked[0]?.algorithm || ''

    return rows.map((row) => ({
      ...row,
      isBest: row.algorithm === bestAlgorithm,
    }))
  }, [routeComparison])

  const comparisonPathPreview = useMemo(() => {
    const path = selectedComparisonResult?.path
    return Array.isArray(path) ? path : []
  }, [selectedComparisonResult])

  const buildWarehouse = async () => {
    const parsedAisles = Number.parseInt(aisleCountInput, 10)
    const parsedShelves = Number.parseInt(shelvesPerAisleInput, 10)

    if (Number.isNaN(parsedAisles) || parsedAisles < 1 || parsedAisles > 20) {
      setError('Aisles must be between 1 and 20.')
      return
    }
    if (Number.isNaN(parsedShelves) || parsedShelves < 1 || parsedShelves > 50) {
      setError('Shelves per aisle must be between 1 and 50.')
      return
    }

    const layout = createLayout(parsedAisles, parsedShelves)
    setLoading(true)
    setError('')

    try {
      const persisted = await createWarehouseMap({
        name: `Warehouse ${parsedAisles}x${parsedShelves}`,
        aisleCount: parsedAisles,
        shelvesPerAisle: parsedShelves,
        grid: layout,
      })

      setWarehouseMapId(persisted?.warehouse_map?.id ?? null)
      setNotice('Warehouse generated and saved. Select robot cards, click shelves for picks, then run orchestration.')
    } catch (requestError) {
      setWarehouseMapId(null)
      setNotice('Warehouse generated locally. Route requests will include the full grid payload.')
      setError(
        requestError?.response?.data?.message ||
          'Could not persist warehouse map. Continuing with local layout only.',
      )
    } finally {
      setBaseLayout(layout)
      setPlannedRobots([])
      setConflictsResolved([])
      setSummary('')
      setCurrentTick(0)
      setMakespan(0)
      setIsAnimating(false)
      setIsConfigured(true)
      setLoading(false)
    }
  }

  const resetWarehouse = () => {
    setIsConfigured(false)
    setBaseLayout([])
    setWarehouseMapId(null)
    setRobotDrafts([createRobotDraft(1), createRobotDraft(2)])
    setPlannedRobots([])
    setConflictsResolved([])
    setSummary('')
    setCurrentTick(0)
    setMakespan(0)
    setIsAnimating(false)
    setError('')
    setNotice('Configure aisles and shelves, then set starts and shelf picks by clicking cells.')
    setSelectedRobotIndex(0)
    setGridClickMode('stop')
  }

  const updateRobotDraft = (index, field, value) => {
    setRobotDrafts((current) =>
      current.map((robot, robotIndex) =>
        robotIndex === index ? { ...robot, [field]: value } : robot,
      ),
    )
  }

  const addRobotDraft = () => {
    setRobotDrafts((current) => [...current, createRobotDraft(current.length + 1, baseLayout[0]?.length || 2)])
    setSelectedRobotIndex(robotDrafts.length)
  }

  const removeRobotDraft = (index) => {
    setRobotDrafts((current) => current.filter((_, robotIndex) => robotIndex !== index))
    setSelectedRobotIndex((current) => {
      if (current === index) {
        return 0
      }
      if (current > index) {
        return current - 1
      }
      return current
    })
  }

  const normalizeRobots = () => {
    if (!baseLayout.length) {
      throw new Error('Generate a warehouse map before planning robot routes.')
    }

    const rows = baseLayout.length
    const cols = baseLayout[0].length
    const ids = new Set()

    return robotDrafts.map((robot, index) => {
      const id = String(robot.id || '').trim()
      const startRow = Number.parseInt(robot.startRow, 10)
      const startCol = Number.parseInt(robot.startCol, 10)
      const stops = Array.isArray(robot.stops) ? robot.stops : []
      const priority = Number.parseInt(robot.priority, 10)

      if (!id) {
        throw new Error(`Robot #${index + 1} needs an ID.`)
      }
      if (ids.has(id)) {
        throw new Error(`Robot ID '${id}' is duplicated.`)
      }
      ids.add(id)

      if ([startRow, startCol, priority].some((value) => Number.isNaN(value))) {
        throw new Error(`Robot '${id}' has invalid numeric coordinates or priority.`)
      }

      if (!stops.length) {
        throw new Error(`Robot '${id}' must have at least one stop.`)
      }

      if (
        startRow < 0 ||
        startCol < 0 ||
        startRow >= rows ||
        startCol >= cols
      ) {
        throw new Error(`Robot '${id}' start is out of bounds.`)
      }

      if (baseLayout[startRow][startCol] === 1) {
        throw new Error(`Robot '${id}' start cannot be placed on shelf cells.`)
      }

      stops.forEach((stop, stopIndex) => {
        const stopRow = stop[0]
        const stopCol = stop[1]
        if (stopRow < 0 || stopCol < 0 || stopRow >= rows || stopCol >= cols) {
          throw new Error(`Robot '${id}' has out-of-bounds stop at index ${stopIndex + 1}.`)
        }
        if (baseLayout[stopRow][stopCol] !== 1) {
          throw new Error(`Robot '${id}' stop at index ${stopIndex + 1} must be a shelf cell.`)
        }
      })

      const goal = stops[stops.length - 1]

      return {
        id,
        start: [startRow, startCol],
        stops,
        goal,
        priority,
      }
    })
  }

  const planRoutes = async () => {
    if (robotDrafts.length < 2) {
      setError('Add at least two robots for multi-agent orchestration.')
      return
    }

    setLoading(true)
    setError('')
    setComparisonLoading(true)

    try {
      const normalizedRobots = normalizeRobots()
      const response = await getOptimalRoute({
        robots: normalizedRobots,
        warehouseMapId,
        grid: warehouseMapId ? null : baseLayout,
      })

      const comparisonRobot = normalizedRobots[selectedRobotIndex] || normalizedRobots[0]
      if (comparisonRobot) {
        const comparisonPayload = {
          start: comparisonRobot.start,
          pickingList: comparisonRobot.stops,
          warehouseMapId,
          grid: warehouseMapId ? null : baseLayout,
          maxAlternatives: 6,
        }

        const comparisonResults = await Promise.allSettled(
          comparisonAlgorithms.map(async (algorithm) => {
            const routeResponse = await getOptimalRoute({
              ...comparisonPayload,
              algorithm,
            })

            return [algorithm, routeResponse]
          }),
        )

        const comparisonMap = {}
        comparisonResults.forEach((entry, index) => {
          if (entry.status === 'fulfilled') {
            const [algorithm, routeResponse] = entry.value
            comparisonMap[algorithm] = routeResponse
            return
          }

          comparisonMap[comparisonAlgorithms[index]] = {
            algorithm: comparisonAlgorithms[index],
            distance: 0,
            path: [],
            summary: 'Comparison failed for this algorithm.',
          }
        })

        setRouteComparison(comparisonMap)
      }

      if (response?.status !== 'success' || !Array.isArray(response.robots)) {
        throw new Error('Unexpected response format from orchestrator.')
      }

      setPlannedRobots(response.robots)
      setConflictsResolved(Array.isArray(response.conflicts_resolved) ? response.conflicts_resolved : [])
      setSummary(response.summary || '')
      setMakespan(response.makespan ?? 0)
      setCurrentTick(0)
      setIsAnimating(true)
      setNotice('Multi-robot orchestration is ready. The algorithm comparison panel is available below.')
    } catch (requestError) {
      setPlannedRobots([])
      setConflictsResolved([])
      setSummary('')
      setCurrentTick(0)
      setMakespan(0)
      setIsAnimating(false)
      setRouteComparison({})
      setError(
        requestError?.response?.data?.message ||
          requestError.message ||
          'Unable to compute multi-robot orchestration.',
      )
    } finally {
      setLoading(false)
      setComparisonLoading(false)
    }
  }

  const replayAnimation = () => {
    if (!plannedRobots.length) {
      return
    }

    setCurrentTick(0)
    setIsAnimating(true)
  }

  return (
    <main className="warehouse-page">
      <div className="warehouse-shell">
        <header className="warehouse-header">
          <div>
            <p className="eyebrow">Multi-agent spatiotemporal orchestrator</p>
            <h1>Priority auctions with collision-free robot motion</h1>
            <p>
              Define a warehouse map, register robots with priorities and stop lists, and watch simultaneous movement over
              shared time steps.
            </p>
          </div>
          <div className="status-card">
            <strong>Live status</strong>
            <p>{notice}</p>
            {plannedRobots.length ? <p>Current tick: {currentTick}</p> : null}
            {plannedRobots.length ? <p>Makespan: {makespan}</p> : null}
          </div>
        </header>

        {!isConfigured ? (
          <section className="setup-card">
            <h2>Step 1: Configure warehouse</h2>
            <p>Set aisle and shelf dimensions before planning robot traffic.</p>

            <div className="form-grid">
              <label>
                Number of aisles
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={aisleCountInput}
                  onChange={(event) => setAisleCountInput(event.target.value)}
                />
              </label>
              <label>
                Shelves per aisle
                <input
                  type="number"
                  min="1"
                  max="50"
                  value={shelvesPerAisleInput}
                  onChange={(event) => setShelvesPerAisleInput(event.target.value)}
                />
              </label>
            </div>

            <button type="button" className="primary-button" onClick={buildWarehouse} disabled={loading}>
              {loading ? 'Generating...' : 'Generate Warehouse'}
            </button>

            {error ? <p className="error-box">{error}</p> : null}
          </section>
        ) : (
          <section className="main-grid">
            <aside className="panel">
              <h2>Step 2: Define robots and shelf picks</h2>
              <p>Map ID: {warehouseMapId ?? 'local-only'}</p>

              <div className="step-options-card">
                <strong>How this system works</strong>
                <div className="step-options-list">
                  <div className="step-option-item">
                    <p>1. Build a warehouse with aisle rows and shelf rows.</p>
                    <p className="step-option-values">Shelves are stock locations, floor cells are movement lanes.</p>
                  </div>
                  <div className="step-option-item">
                    <p>2. Configure robots, set priorities, and choose each robot.</p>
                    <p className="step-option-values">Higher priority robots usually keep shorter detours in conflicts.</p>
                  </div>
                  <div className="step-option-item">
                    <p>3. Pick mode:</p>
                    <p className="step-option-values">Set Start mode: click floor to place start. Pick Shelves mode: click shelf cells to add/remove stock picks.</p>
                  </div>
                  <div className="step-option-item">
                    <p>4. Run orchestration.</p>
                    <p className="step-option-values">Planner computes collision-free, time-synchronized paths and logs conflict resolutions.</p>
                  </div>
                </div>
              </div>

              <div className="route-options-card">
                <strong>Options</strong>
                <p>Selected robot: {activeRobotId || 'None'}</p>
                <label className="algorithm-picker">
                  Compare algorithm
                  <select value={routingAlgorithm} onChange={(event) => setRoutingAlgorithm(event.target.value)}>
                    <option value="A*">A*</option>
                    <option value="Greedy Best-First Search">Greedy Best-First Search</option>
                    <option value="Floyd-Warshall">Floyd-Warshall</option>
                  </select>
                </label>
                <p className="route-summary">
                  {selectedComparisonResult
                    ? 'Switch the selector below to compare how each algorithm routes the selected robot.'
                    : 'Run orchestration once to load the algorithm comparison table.'}
                </p>
              </div>

              <div className="route-options-card">
                <strong>Algorithm comparison</strong>
                <p>
                  Preview for {activeRobotId || 'the selected robot'}
                  {comparisonLoading ? ' is loading...' : ''}
                </p>
                <div className="route-path-preview" aria-label="path preview">
                  {comparisonPathPreview.length ? (
                    comparisonPathPreview.map((cell, index) => (
                      <span key={`${routingAlgorithm}-${index}`} className="path-chip">
                        [{cell[0]}, {cell[1]}]
                      </span>
                    ))
                  ) : (
                    <span className="muted">No comparison path available yet.</span>
                  )}
                </div>
              </div>

              {routeComparisonRows.length ? (
                <div className="route-options-card">
                  <strong>Algorithm comparison table</strong>
                  <table className="comparison-table">
                    <thead>
                      <tr>
                        <th>Algorithm</th>
                        <th>Distance</th>
                        <th>Path steps</th>
                        <th>Verdict</th>
                      </tr>
                    </thead>
                    <tbody>
                      {routeComparisonRows.map((row) => (
                        <tr key={row.algorithm} className={row.isBest ? 'comparison-best' : ''}>
                          <td>{row.algorithm}</td>
                          <td>{row.distance}</td>
                          <td>{row.pathLength}</td>
                          <td>{row.isBest ? 'Best overall' : 'Slower than best'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}

              <div className="legend-row">
                <span className="badge floor">Floor</span>
                <span className="badge shelf">Shelf</span>
                <span className="badge goal">Goal</span>
                <span className="badge stop">Shelf Pick</span>
                <span className="badge robot">Robot</span>
                <span className="badge yielding">Yielding</span>
              </div>

              <div className="robot-editor-list">
                {robotDrafts.map((robot, index) => (
                  <div
                    key={`robot-editor-${index}`}
                    className={`robot-editor-card ${selectedRobotIndex === index ? 'robot-editor-card-active' : ''}`}
                  >
                    <div className="robot-editor-header">
                      <strong>Robot {index + 1}</strong>
                      <button
                        type="button"
                        className="text-button"
                        onClick={() => setSelectedRobotIndex(index)}
                      >
                        {selectedRobotIndex === index ? 'Selected' : 'Select'}
                      </button>
                      {robotDrafts.length > 2 ? (
                        <button
                          type="button"
                          className="text-button"
                          onClick={() => removeRobotDraft(index)}
                        >
                          Remove
                        </button>
                      ) : null}
                    </div>

                    <div className="robot-editor-grid">
                      <label>
                        ID
                        <input
                          type="text"
                          value={robot.id}
                          onChange={(event) => updateRobotDraft(index, 'id', event.target.value)}
                        />
                      </label>
                      <label>
                        Priority
                        <input
                          type="number"
                          min="1"
                          max="10"
                          value={robot.priority}
                          onChange={(event) => updateRobotDraft(index, 'priority', event.target.value)}
                        />
                      </label>
                      <label>
                        Start row
                        <input
                          type="number"
                          min="0"
                          value={robot.startRow}
                          onChange={(event) => updateRobotDraft(index, 'startRow', event.target.value)}
                        />
                      </label>
                      <label>
                        Start col
                        <input
                          type="number"
                          min="0"
                          value={robot.startCol}
                          onChange={(event) => updateRobotDraft(index, 'startCol', event.target.value)}
                        />
                      </label>
                      <label>
                        Selected shelf picks: {Array.isArray(robot.stops) ? robot.stops.length : 0}
                        <div className="picked-items">
                          {Array.isArray(robot.stops) && robot.stops.length ? (
                            robot.stops.map((stop, stopIndex) => (
                              <span key={`stop-${index}-${stopIndex}`}>[{stop[0]}, {stop[1]}]</span>
                            ))
                          ) : (
                            <span className="muted">No shelf picks selected yet</span>
                          )}
                        </div>
                      </label>
                      <label>
                        Actions
                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => updateRobotDraft(index, 'stops', [])}
                        >
                          Clear Picks
                        </button>
                      </label>
                    </div>
                  </div>
                ))}
              </div>

              <button type="button" className="secondary-button" onClick={addRobotDraft}>
                Add robot
              </button>

              <button type="button" className="primary-button" onClick={planRoutes} disabled={loading}>
                {loading ? 'Orchestrating...' : 'Run Multi-Robot Orchestration'}
              </button>

              <button type="button" className="secondary-button" onClick={replayAnimation}>
                Replay animation
              </button>

              <button type="button" className="secondary-button" onClick={resetWarehouse}>
                Reconfigure Warehouse
              </button>

              {summary ? <p className="route-summary">{summary}</p> : null}

              {robotStateRows.length ? (
                <div className="state-list">
                  <strong>Robot states</strong>
                  {robotStateRows.map((robot) => (
                    <div
                      key={`robot-state-${robot.id}`}
                      className={`state-chip ${robot.flash ? 'state-chip-flash' : ''}`}
                    >
                      <span>{robot.id}</span>
                      <span>P{robot.priority}</span>
                      <span>{robot.state}</span>
                    </div>
                  ))}
                </div>
              ) : null}

              {plannedRobots.length ? (
                <div className="picking-card">
                  <strong>Stock pickup details</strong>
                  <p>Each shelf stop is served when the robot reaches an adjacent floor cell.</p>
                  <div className="step-options-list">
                    {plannedRobots.map((robot) => (
                      <div key={`served-${robot.id}`} className="step-option-item">
                        <p>
                          {robot.id} requested: {JSON.stringify(robot.stops || [])}
                        </p>
                        <p className="step-option-values">
                          serviced from: {JSON.stringify(robot.serviced_from || [])}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {conflictsResolved.length ? (
                <div className="step-options-card">
                  <strong>Conflict log</strong>
                  <div className="step-options-list">
                    {conflictsResolved.slice(0, 10).map((entry, index) => (
                      <div key={`conflict-${index}`} className="step-option-item">
                        <p>
                          t={entry.time} | {entry.type} conflict | yielded: {entry.yielded_robot}
                        </p>
                        <p className="step-option-values">
                          {entry.robots?.join(' vs ')} | detour: {JSON.stringify(entry.detour_costs)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {error ? <p className="error-box">{error}</p> : null}
            </aside>

            <section className="grid-card">
              <div className="grid-title">
                <h2>Spatiotemporal grid playback</h2>
                <span>{plannedRobots.length ? `t = ${currentTick}` : 'Idle'}</span>
              </div>

              <div
                className="warehouse-grid"
                style={{ gridTemplateColumns: `repeat(${baseLayout[0]?.length ?? 1}, 1fr)` }}
              >
                {baseLayout.map((row, rowIndex) =>
                  row.map((cellType, colIndex) => {
                    const key = getCellKey(rowIndex, colIndex)
                    const robotsHere = robotPositionsByCell.get(key) || []
                    const hasGoal = robotGoals.has(key)
                    const stopMarkers = draftStopsByCell.get(key) || []
                    const hasStop = stopMarkers.length > 0
                    const hasActiveStop = isActiveRobotStop(rowIndex, colIndex)
                    const isSelectable =
                      (gridClickMode === 'start' && cellType !== 1) ||
                      (gridClickMode === 'stop' && cellType === 1)

                    return (
                      <div
                        key={key}
                        className={getCellClassName(
                          cellType,
                          hasGoal,
                          hasStop,
                          hasActiveStop,
                          isSelectable,
                        )}
                        title={`(${rowIndex}, ${colIndex})`}
                        onClick={() => onGridCellClick(rowIndex, colIndex, cellType)}
                      >
                        {hasStop ? (
                          <span className="stop-marker" title={stopMarkers.map((x) => x.robotId).join(', ')}>
                            {stopMarkers.length}
                          </span>
                        ) : null}
                        {robotsHere.map((robotId) => (
                          <span key={`${key}-${robotId}`} className="robot-token">
                            {robotId}
                          </span>
                        ))}
                      </div>
                    )
                  }),
                )}
              </div>
            </section>
          </section>
        )}
      </div>
    </main>
  )
}

export default WarehouseGrid