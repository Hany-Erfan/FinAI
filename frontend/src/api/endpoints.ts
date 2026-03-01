export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const VECTOR_DB_BASE = import.meta.env.VITE_VECTOR_DB_URL || 'http://localhost:8004/vector_db_service';
export const GUARDRAILS_BASE = import.meta.env.VITE_GUARDRAILS_URL || 'http://localhost:8005';

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
  GUARDRAILS_CONFIG: `${GUARDRAILS_BASE}/config`
} as const;

