import axios from 'axios';

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001';

// Default 180 s — most endpoints respond quickly but the analytics pipeline
// involves two LLM round-trips (SQL generation + insight generation) plus RAG
// retrieval, which can collectively take 90–120 s on this machine.
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 180000, // 180 s default
});

// For /analytics/run specifically, allow up to 4 minutes so a slow LLM day
// never silently cuts off the pipeline mid-flight.
apiClient.interceptors.request.use((config) => {
  if (config.url?.includes('/analytics/run')) {
    config.timeout = 240000; // 240 s (4 min)
  }
  return config;
});

export default apiClient;
