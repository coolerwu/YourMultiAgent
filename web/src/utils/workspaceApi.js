/**
 * utils/workspaceApi.js
 * Workspace CRUD API。
 */

import { api, wsRun } from './api'

export const workspaceApi = {
  list: () => api.get('/api/workspaces'),
  get: (id) => api.get(`/api/workspaces/${id}`),
  create: (data) => api.post('/api/workspaces', data),
  update: (id, data) => api.put(`/api/workspaces/${id}`, data),
  delete: (id) => api.delete(`/api/workspaces/${id}`),
  getOrchestration: (id) => api.get(`/api/workspaces/${id}/orchestration`),
  listSessions: (id) => api.get(`/api/workspaces/${id}/sessions`),
  createSession: (id, data = {}) => api.post(`/api/workspaces/${id}/sessions`, data),
  getSession: (id, sessionId) => api.get(`/api/workspaces/${id}/sessions/${sessionId}`),
  deleteSession: (id, sessionId) => api.delete(`/api/workspaces/${id}/sessions/${sessionId}`),
  updateOrchestration: (id, data) => api.put(`/api/workspaces/${id}/orchestration`, data),
  run: (id, payload, onChunk, onDone, onError) =>
    wsRun(`/ws/workspaces/${id}/run`, payload, onChunk, onDone, onError),
}
