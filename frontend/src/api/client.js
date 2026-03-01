import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const resp = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
          localStorage.setItem('access_token', resp.data.access_token)
          localStorage.setItem('refresh_token', resp.data.refresh_token)
          originalRequest.headers.Authorization = `Bearer ${resp.data.access_token}`
          return api(originalRequest)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

// Auth
export const login = (email, password) => api.post('/auth/login', { email, password })
export const register = (data) => api.post('/auth/register', data)
export const getMe = () => api.get('/users/me')

// Teams
export const fetchTeams = () => api.get('/teams')
export const createTeam = (data) => api.post('/teams', data)

// Users
export const fetchUsers = () => api.get('/users')
export const updateUser = (id, data) => api.put(`/users/${id}`, data)

// Calls (existing, now auth-protected)
export async function fetchCalls() {
  const { data } = await api.get('/calls')
  return data
}

export async function fetchCallDetail(id) {
  const { data } = await api.get(`/calls/${id}`)
  return data
}

export async function fetchCallStatus(id) {
  const { data } = await api.get(`/calls/${id}/status`)
  return data
}

export async function fetchDashboardStats() {
  const { data } = await api.get('/calls/stats')
  return data
}

export async function uploadAudio(file, title) {
  const form = new FormData()
  form.append('file', file)
  form.append('title', title || file.name)
  const { data } = await api.post('/calls/upload', form)
  return data
}

export async function deleteCall(id) {
  const { data } = await api.delete(`/calls/${id}`)
  return data
}

export async function fetchCallScores(id) {
  const { data } = await api.get(`/calls/${id}/scores`)
  return data
}

export async function fetchCallReview(id) {
  const { data } = await api.get(`/calls/${id}/review`)
  return data
}

export async function submitReview(id, review) {
  const { data } = await api.post(`/calls/${id}/review`, review)
  return data
}

// Audit log
export const fetchAuditLog = (params) => api.get('/audit-log', { params })

export function audioUrl(filename) {
  return `/audio/${filename}`
}

export default api
