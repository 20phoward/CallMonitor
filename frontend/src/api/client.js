import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

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

export function audioUrl(filename) {
  return `/audio/${filename}`
}
