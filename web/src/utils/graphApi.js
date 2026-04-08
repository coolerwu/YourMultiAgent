/**
 * utils/graphApi.js
 * Agent Graph CRUD + 运行 API。
 * run() 使用 WebSocket 替代 SSE。
 */

import { api, wsRun } from './api'

export const graphApi = {
  list: () => api.get('/api/graphs'),
  get: (id) => api.get(`/api/graphs/${id}`),
  create: (data) => api.post('/api/graphs', data),
  update: (id, data) => api.put(`/api/graphs/${id}`, data),
  delete: (id) => api.delete(`/api/graphs/${id}`),
  optimizePrompt: (data) => api.post('/api/agents/prompt-optimize', data),
  generateWorker: (data) => api.post('/api/agents/worker-generate', data),
  /** 流式执行，返回 WebSocket 实例（可调用 .close() 中止） */
  run: (id, userMessage, onChunk, onDone, onError) =>
    wsRun(`/ws/graphs/${id}/run`, { user_message: userMessage }, onChunk, onDone, onError),
}

export const workerApi = {
  listCapabilities: () => api.get('/api/workers/capabilities'),
  listWorkers: () => api.get('/api/workers'),
  updateEnabledCapabilities: (workerId, capabilityNames) =>
    api.put(`/api/workers/${workerId}/enabled-capabilities`, { capability_names: capabilityNames }),
}
