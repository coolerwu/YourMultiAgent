/**
 * utils/graphApi.js
 * Agent Graph CRUD + 运行 API。
 */

import { api, streamPost } from './api'

export const graphApi = {
  list: () => api.get('/api/graphs'),
  get: (id) => api.get(`/api/graphs/${id}`),
  create: (data) => api.post('/api/graphs', data),
  update: (id, data) => api.put(`/api/graphs/${id}`, data),
  delete: (id) => api.delete(`/api/graphs/${id}`),
  run: (id, userMessage, onChunk, onDone) =>
    streamPost(`/api/graphs/${id}/run`, { user_message: userMessage }, onChunk, onDone),
}

export const workerApi = {
  listCapabilities: () => api.get('/api/workers/capabilities'),
}
