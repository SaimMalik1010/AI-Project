import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

export const getOptimalRoute = async (pickingList, start = [0, 0]) => {
  const response = await apiClient.post('/get-route/', {
    start,
    targets: pickingList,
  })

  return response.data
}

export default apiClient