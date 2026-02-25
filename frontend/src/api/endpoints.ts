export const API_BASE = 'http://localhost:8000';

export const Endpoints = {
  LOGIN: `${API_BASE}/login`,
  CHAT: `${API_BASE}/chat`, 
  CURRENT_USER: `${API_BASE}/currentUser`,
  LOGOUT: `${API_BASE}/logout`,
  ADMIN_MANAGEMENT: `${API_BASE}/admin/management`
} as const;


