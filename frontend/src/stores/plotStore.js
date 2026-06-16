import { defineStore } from 'pinia'
import { ref } from 'vue'

const API = (path) => `/api${path}`

async function apiFetch(path, options = {}) {
  const res = await fetch(API(path), {
    headers: options.body ? { 'Content-Type': 'application/json' } : {},
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || err.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export const usePlotStore = defineStore('plot', () => {
  const plots = ref([])
  const currentPlot = ref(null)
  const characters = ref([])
  const sessions = ref([])
  const lorebooks = ref([])

  async function fetchPlots() {
    plots.value = await apiFetch('/plots')
  }

  async function fetchPlot(id) {
    currentPlot.value = await apiFetch(`/plots/${id}`)
    characters.value = currentPlot.value.characters || []
    return currentPlot.value
  }

  async function fetchSessions(plotId) {
    sessions.value = await apiFetch(`/sessions?plot_id=${plotId}`)
    return sessions.value
  }

  async function createSession(plotId, title = '新会话') {
    return apiFetch('/sessions', {
      method: 'POST',
      body: JSON.stringify({ plot_id: plotId, title }),
    })
  }

  async function fetchLorebooks() {
    lorebooks.value = await apiFetch('/lorebooks')
    return lorebooks.value
  }

  async function fetchTask(taskId) {
    return apiFetch(`/tasks/${taskId}`)
  }

  async function publishPlot(plotId) {
    await apiFetch(`/plots/${plotId}/publish`, { method: 'PUT' })
  }

  async function updatePlot(plotId, data) {
    await apiFetch(`/plots/${plotId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
    // 后端只返回 {ok: true}，手动更新本地列表
    const idx = plots.value.findIndex(p => p.id === plotId)
    if (idx >= 0) {
      const updated = { ...plots.value[idx] }
      for (const [k, v] of Object.entries(data)) {
        updated[k] = v
      }
      plots.value[idx] = updated
    }
  }

  async function deletePlot(plotId) {
    await apiFetch(`/plots/${plotId}`, { method: 'DELETE' })
    await fetchPlots()
  }

  return {
    plots, currentPlot, characters, sessions, lorebooks,
    fetchPlots, fetchPlot, fetchSessions, createSession,
    fetchLorebooks, fetchTask, publishPlot, updatePlot, deletePlot,
  }
})
