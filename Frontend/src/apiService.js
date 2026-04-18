import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

export const createWarehouseMap = async ({ name, aisleCount, shelvesPerAisle, grid }) => {
  const response = await apiClient.post('/warehouse-maps/create/', {
    name,
    aisle_count: aisleCount,
    shelves_per_aisle: shelvesPerAisle,
    grid,
  })

  return response.data
}

export const getWarehouseMap = async (mapId) => {
  const response = await apiClient.get(`/warehouse-maps/${mapId}/`)
  return response.data
}

export const listWarehouseMaps = async () => {
  const response = await apiClient.get('/warehouse-maps/')
  return response.data
}

export const getOptimalRoute = async ({
  pickingList,
  start = [0, 0],
  warehouseMapId = null,
  grid = null,
}) => {
  const payload = {
    start,
    targets: pickingList,
  }

  if (warehouseMapId !== null && warehouseMapId !== undefined) {
    payload.warehouse_map_id = warehouseMapId
  }

  if (grid) {
    payload.grid = grid
  }

  const response = await apiClient.post('/get-route/', {
    ...payload,
  })

  return response.data
}

export default apiClient