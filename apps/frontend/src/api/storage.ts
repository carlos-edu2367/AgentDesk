import { api } from './client'
import type { HealthResponse, StorageInfo } from '../types/domain'

export const healthApi = {
  check: () => api.get<HealthResponse>('/api/health'),
}

export const storageApi = {
  info: () => api.get<StorageInfo>('/api/storage/info'),
}
