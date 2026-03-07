export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const VECTOR_DB_BASE = import.meta.env.VITE_VECTOR_DB_URL || 'http://localhost:8004/vector_db_service';
export const GUARDRAILS_BASE = import.meta.env.VITE_GUARDRAILS_URL || 'http://localhost:8005';
export const REPOSITORY_BASE = import.meta.env.REPOSITORY_URL || 'http://localhost:8007';

export const Endpoints = {
  LOGIN: `${API_BASE}/login`,
  CHAT: `${API_BASE}/chat`,
  BACKOFFICE_UPLOAD: `${VECTOR_DB_BASE}/upload`,
  BACKOFFICE_PRODUCTS: `${VECTOR_DB_BASE}/products`,
  BACKOFFICE_DELETE: (id: string) => `${VECTOR_DB_BASE}/delete/${id}`,
  BACKOFFICE_CLEAR: `${VECTOR_DB_BASE}/clear`,
  BACKOFFICE_UPSERT: `${VECTOR_DB_BASE}/upsert`,
  CURRENT_USER: `${API_BASE}/currentUser`,
  LOGOUT: `${API_BASE}/logout`,
  SUMMARY: `${API_BASE}/summary`,
  GUARDRAILS_CONFIG: `${GUARDRAILS_BASE}/config`,
  GET_MESSAGES: (session_id: string) => `${REPOSITORY_BASE}/sessions/${session_id}/messages`,
} as const;

