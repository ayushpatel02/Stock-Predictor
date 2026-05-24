import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

// Log errors in development
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (import.meta.env.DEV) {
      console.error('[API error]', err.response?.status, err.config?.url, err.response?.data)
    }
    return Promise.reject(err)
  }
)

export const fetchMarketOverview = () => api.get('/market/overview').then((r) => r.data)

export const fetchUniverse = () => api.get('/universe').then((r) => r.data)

export const fetchStock = (symbol) => api.get(`/stocks/${symbol}`).then((r) => r.data)

export const fetchPrediction = (symbol) =>
  api.get(`/stocks/${symbol}/predict`).then((r) => r.data)

export const fetchDvm = (symbol) =>
  api.get(`/stocks/${symbol}/dvm`).then((r) => r.data)

export const fetchNews = (symbol, limit = 10) =>
  api.get(`/stocks/${symbol}/news`, { params: { limit } }).then((r) => r.data)

export const fetchPeers = (symbol, n = 5) =>
  api.get(`/stocks/${symbol}/peers`, { params: { n } }).then((r) => r.data)

export const fetchScreener = () => api.get('/screener/all').then((r) => r.data)

export const fetchTechnicals = (symbol) =>
  api.get(`/stocks/${symbol}/technicals`).then((r) => r.data)

export const fetchOverview = (symbol) =>
  api.get(`/stocks/${symbol}/overview`).then((r) => r.data)

export const runBacktest = (symbol) =>
  api.post(`/backtest/${symbol}`).then((r) => r.data)

export default api
