import { useEffect, useMemo, useState } from 'react'

import { createWarehouseMap, getOptimalRoute } from './apiService.js'
import './WarehouseGrid.css'

const START_CELL = [0, 0]
const getCellKey = (row, col) => `${row}-${col}`

const createLayout = (aisleCount, shelvesPerAisle) => {
  const rows = aisleCount * 2 + 1
  const cols = shelvesPerAisle + 2
  const layout = Array.from({ length: rows }, () => Array.from({ length: cols }, () => 0))

  layout[START_CELL[0]][START_CELL[1]] = 2

  // Each aisle is one shelf row, separated by one walking row.
  for (let aisle = 0; aisle < aisleCount; aisle += 1) {
    const row = aisle * 2 + 1
    for (let col = 1; col <= shelvesPerAisle; col += 1) {
      layout[row][col] = 1
    }
  }

  return layout
}

const getCellClassName = (cellType, isCurrentStep, visitCount = 0) => {
  if (cellType === 2) return 'cell cell-start'
  if (cellType === 3) return 'cell cell-target'
  if (cellType === 4) {
    const intensityClass =
      visitCount >= 3 ? 'cell-path-3' : visitCount === 2 ? 'cell-path-2' : 'cell-path-1'
    return isCurrentStep
      ? `cell cell-path ${intensityClass} cell-path-current`
      : `cell cell-path ${intensityClass}`
  }
  if (cellType === 1) return 'cell cell-shelf'
  return 'cell cell-floor'
}

function WarehouseGrid() {
  const [aisleCountInput, setAisleCountInput] = useState('4')
  const [shelvesPerAisleInput, setShelvesPerAisleInput] = useState('12')
  const [aisleCount, setAisleCount] = useState(4)
  const [shelvesPerAisle, setShelvesPerAisle] = useState(12)
  const [isConfigured, setIsConfigured] = useState(false)
  const [warehouseMapId, setWarehouseMapId] = useState(null)

  const [baseLayout, setBaseLayout] = useState([])
  const [pickingList, setPickingList] = useState([])
  const [routeOptions, setRouteOptions] = useState([])
  const [selectedRouteIndex, setSelectedRouteIndex] = useState(0)
  const [stepOptions, setStepOptions] = useState([])
  const [routeSummary, setRouteSummary] = useState('')
  const [routePath, setRoutePath] = useState([])
  const [revealedSteps, setRevealedSteps] = useState(0)
  const [routeDistance, setRouteDistance] = useState(null)
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('Configure aisles and shelves, then click Generate Warehouse.')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!routePath.length) {
      setRevealedSteps(0)
      return undefined
    }

    setRevealedSteps(0)
    const timers = routePath.map((_, index) =>
      window.setTimeout(() => {
        setRevealedSteps(index + 1)
      }, index * 140),
    )

    return () => {
      timers.forEach((timerId) => window.clearTimeout(timerId))
    }
  }, [routePath])

  const displayLayout = useMemo(() => {
    if (!baseLayout.length) return []

    const nextLayout = baseLayout.map((row) => [...row])

    pickingList.forEach(([row, col]) => {
      if (nextLayout[row]?.[col] === 1) {
        nextLayout[row][col] = 3
      }
    })

    routePath.slice(0, revealedSteps).forEach(([row, col]) => {
      if (
        nextLayout[row]?.[col] !== 1 &&
        nextLayout[row]?.[col] !== 2 &&
        nextLayout[row]?.[col] !== 3
      ) {
        nextLayout[row][col] = 4
      }
    })

    return nextLayout
  }, [baseLayout, pickingList, routePath, revealedSteps])

  const pathVisitMeta = useMemo(() => {
    const countByCell = new Map()
    const visiblePath = routePath.slice(0, revealedSteps)

    visiblePath.forEach(([row, col]) => {
      const key = getCellKey(row, col)
      countByCell.set(key, (countByCell.get(key) ?? 0) + 1)
    })

    const currentStep = visiblePath[visiblePath.length - 1]
    const currentStepKey = currentStep ? getCellKey(currentStep[0], currentStep[1]) : null

    return {
      countByCell,
      currentStepKey,
    }
  }, [routePath, revealedSteps])

  const selectedTargetLabel = pickingList.length
    ? `${pickingList.length} target${pickingList.length === 1 ? '' : 's'} selected`
    : 'No targets selected yet'

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

      const persistedMap = persisted?.warehouse_map

      setAisleCount(parsedAisles)
      setShelvesPerAisle(parsedShelves)
      setBaseLayout(layout)
      setPickingList([])
      setRouteOptions([])
      setSelectedRouteIndex(0)
      setStepOptions([])
      setRouteSummary('')
      setRoutePath([])
      setRouteDistance(null)
      setWarehouseMapId(persistedMap?.id ?? null)
      setIsConfigured(true)
      setNotice('Warehouse generated and saved. Click shelf cells to choose picking targets.')
    } catch (requestError) {
      setAisleCount(parsedAisles)
      setShelvesPerAisle(parsedShelves)
      setBaseLayout(layout)
      setPickingList([])
      setRouteOptions([])
      setSelectedRouteIndex(0)
      setStepOptions([])
      setRouteSummary('')
      setRoutePath([])
      setRouteDistance(null)
      setWarehouseMapId(null)
      setIsConfigured(true)
      setNotice('Warehouse generated locally. Backend save failed, route calls will send full grid.')
      setError(
        requestError?.response?.data?.message ||
          'Could not persist the warehouse map. Continuing with local map data.',
      )
    } finally {
      setLoading(false)
    }
  }

  const resetWarehouse = () => {
    setIsConfigured(false)
    setBaseLayout([])
    setPickingList([])
    setRouteOptions([])
    setSelectedRouteIndex(0)
    setStepOptions([])
    setRouteSummary('')
    setRoutePath([])
    setRouteDistance(null)
    setWarehouseMapId(null)
    setError('')
    setNotice('Configure aisles and shelves, then click Generate Warehouse.')
  }

  const toggleTargetCell = (rowIndex, colIndex) => {
    const cellState = baseLayout[rowIndex]?.[colIndex]

    if (cellState !== 1) {
      return
    }

    setPickingList((currentList) => {
      const existingIndex = currentList.findIndex(([row, col]) => row === rowIndex && col === colIndex)

      if (existingIndex >= 0) {
        setNotice(`Removed target (${rowIndex}, ${colIndex}) from the picking list.`)
        return currentList.filter(([row, col]) => row !== rowIndex || col !== colIndex)
      }

      setNotice(`Added target (${rowIndex}, ${colIndex}) to the picking list.`)
      return [...currentList, [rowIndex, colIndex]]
    })
  }

  const calculateRoute = async () => {
    if (!pickingList.length) {
      setError('Select at least one shelf target before calculating a route.')
      return
    }

    setLoading(true)
    setError('')
    setNotice('Requesting an optimized route from the backend...')

    try {
      const response = await getOptimalRoute({
        pickingList,
        start: START_CELL,
        warehouseMapId,
        grid: warehouseMapId ? null : baseLayout,
        maxAlternatives: 8,
      })

      if (response?.status === 'success') {
        const nextOptions =
          Array.isArray(response.route_options) && response.route_options.length
            ? response.route_options
            : [
                {
                  rank: 1,
                  path: Array.isArray(response.path) ? response.path : [],
                  distance: response.distance ?? null,
                  is_best: true,
                  label: 'Best path',
                },
              ]

        setRouteOptions(nextOptions)
        setSelectedRouteIndex(0)
        setRoutePath(Array.isArray(nextOptions[0]?.path) ? nextOptions[0].path : [])
        setRouteDistance(nextOptions[0]?.distance ?? response.distance ?? null)
        setStepOptions(Array.isArray(response.step_options) ? response.step_options : [])
        setRouteSummary(response.summary || '')
        if (response.warehouse_map_id) {
          setWarehouseMapId(response.warehouse_map_id)
        }
        setNotice('Best route and alternatives received. Use the controls to replay each option.')
      } else {
        setRouteOptions([])
        setSelectedRouteIndex(0)
        setStepOptions([])
        setRouteSummary('')
        setRoutePath([])
        setRouteDistance(null)
        setError('The backend returned an unexpected response.')
      }
    } catch (requestError) {
      setRouteOptions([])
      setSelectedRouteIndex(0)
      setStepOptions([])
      setRouteSummary('')
      setRoutePath([])
      setRouteDistance(null)
      setError(
        requestError?.response?.data?.message ||
          'Unable to reach the backend. Make sure Django is running on port 8000.',
      )
    } finally {
      setLoading(false)
    }
  }

  const selectRouteOption = (nextIndex) => {
    if (nextIndex < 0 || nextIndex >= routeOptions.length) {
      return
    }

    const selectedOption = routeOptions[nextIndex]
    setSelectedRouteIndex(nextIndex)
    setRoutePath(Array.isArray(selectedOption?.path) ? selectedOption.path : [])
    setRouteDistance(selectedOption?.distance ?? null)

    if (selectedOption?.is_best) {
      setNotice('Showing the globally best path.')
    } else {
      setNotice(`Showing alternative route #${nextIndex + 1}.`)
    }
  }

  return (
    <main className="warehouse-page">
      <div className="warehouse-shell">
        <header className="warehouse-header">
          <div>
            <p className="eyebrow">Warehouse route optimizer</p>
            <h1>Step-by-step picking planner</h1>
            <p>
              First define your warehouse structure. After that, click shelves to pick targets and run the route.
            </p>
          </div>
          <div className="status-card">
            <strong>Live status</strong>
            <p>{notice}</p>
            {routeDistance !== null ? <p>Last route distance: {routeDistance}</p> : null}
          </div>
        </header>

        {!isConfigured ? (
          <section className="setup-card">
            <h2>Step 1: Configure warehouse</h2>
            <p>Tell the app how many aisles and shelves you have.</p>

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

            <button type="button" className="primary-button" onClick={buildWarehouse}>
              Generate Warehouse
            </button>

            {error ? <p className="error-box">{error}</p> : null}
          </section>
        ) : (
          <section className="main-grid">
            <aside className="panel">
              <h2>Step 2: Select picking shelves</h2>
              <p>
                Layout: {aisleCount} aisle(s), {shelvesPerAisle} shelf slot(s) per aisle.
              </p>
              <p>
                Map ID: {warehouseMapId ?? 'local-only'}
              </p>

              <div className="legend-row">
                <span className="badge floor">Floor</span>
                <span className="badge shelf">Shelf</span>
                <span className="badge start">Start</span>
                <span className="badge target">Target</span>
                <span className="badge path">Path</span>
              </div>

              <button
                type="button"
                className="primary-button"
                onClick={calculateRoute}
                disabled={loading}
              >
                {loading ? 'Calculating...' : 'Calculate Optimal Route'}
              </button>

              <button type="button" className="secondary-button" onClick={resetWarehouse}>
                Reconfigure Warehouse
              </button>

              <div className="picking-card">
                <strong>Picking list</strong>
                <p>{selectedTargetLabel}</p>
                <div className="picked-items">
                  {pickingList.length ? (
                    pickingList.map(([row, col]) => <span key={`${row}-${col}`}>({row}, {col})</span>)
                  ) : (
                    <span className="muted">No shelves selected yet.</span>
                  )}
                </div>
              </div>

              {routeOptions.length ? (
                <div className="route-options-card">
                  <strong>Route options</strong>
                  <p>
                    Viewing route #{selectedRouteIndex + 1} of {routeOptions.length}.
                  </p>
                  {routeSummary ? <p className="route-summary">{routeSummary}</p> : null}
                  <div className="route-option-actions">
                    <button
                      type="button"
                      className="secondary-button route-switch"
                      onClick={() => selectRouteOption(selectedRouteIndex - 1)}
                      disabled={selectedRouteIndex === 0}
                    >
                      Previous option
                    </button>
                    <button
                      type="button"
                      className="secondary-button route-switch"
                      onClick={() => selectRouteOption(selectedRouteIndex + 1)}
                      disabled={selectedRouteIndex >= routeOptions.length - 1}
                    >
                      Next option
                    </button>
                  </div>
                </div>
              ) : null}

              {stepOptions.length ? (
                <div className="step-options-card">
                  <strong>Step-by-step alternatives (best path)</strong>
                  <div className="step-options-list">
                    {stepOptions.map((step) => (
                      <div key={`step-option-${step.step_index}`} className="step-option-item">
                        <p>
                          Step {step.step_index} at ({step.at[0]}, {step.at[1]})
                        </p>
                        <p className="step-option-values">
                          {step.alternatives.length
                            ? step.alternatives
                                .slice(0, 4)
                                .map((option) => {
                                  const marker = option.is_best_step ? 'best' : 'alt'
                                  return `${marker}: (${option.next[0]}, ${option.next[1]}) -> ${option.estimated_total_distance}`
                                })
                                .join(' | ')
                            : 'No alternatives available'}
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
                <h2>Dynamic warehouse grid</h2>
                <span>
                  {routePath.length ? `${revealedSteps}/${routePath.length} steps shown` : 'Route idle'}
                </span>
              </div>

              <div
                className="warehouse-grid"
                style={{ gridTemplateColumns: `repeat(${displayLayout[0]?.length ?? 1}, 1fr)` }}
              >
                {displayLayout.map((row, rowIndex) =>
                  row.map((cellType, colIndex) => {
                    const key = getCellKey(rowIndex, colIndex)
                    const visitCount = pathVisitMeta.countByCell.get(key) ?? 0
                    const isCurrentStep = pathVisitMeta.currentStepKey === key

                    return (
                      <button
                        type="button"
                        key={`${rowIndex}-${colIndex}`}
                        className={getCellClassName(cellType, isCurrentStep, visitCount)}
                        onClick={() => toggleTargetCell(rowIndex, colIndex)}
                        aria-label={`Cell ${rowIndex}, ${colIndex}`}
                        title={`(${rowIndex}, ${colIndex})`}
                      >
                        {cellType === 2 ? 'S' : ''}
                      </button>
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