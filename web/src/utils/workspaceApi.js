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
  getProviderSettings: () => api.get('/api/settings/providers'),
  updateProviderSettings: (data) => api.put('/api/settings/providers', data),
  getCodexRuntimeSummary: () => api.get('/api/settings/codex/runtime'),
  getAppLog: (lines = 300) => api.get(`/api/settings/logs/app?lines=${lines}`),
  startUpdateNow: () => api.post('/api/admin/update-now', {}),
  getUpdateNowStatus: () => api.get('/api/admin/update-now/current'),
  checkCodexConnection: (id) => api.post(`/api/settings/codex-connections/${id}/check`, {}),
  installCodexConnection: (id) => api.post(`/api/settings/codex-connections/${id}/install`, {}),
  loginCodexConnection: (id) => api.post(`/api/settings/codex-connections/${id}/login`, {}),
  run: (id, payload, onChunk, onDone, onError) =>
    wsRun(`/ws/workspaces/${id}/run`, payload, onChunk, onDone, onError),
}
