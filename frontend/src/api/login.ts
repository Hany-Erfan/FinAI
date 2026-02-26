import { sessionHeaders } from "../utils/authUtils";
import { Endpoints } from "./endpoints";

export async function login(username, password, sessionId) {
  const response = await fetch(`${Endpoints.LOGIN}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ username, password, session_id: sessionId }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(err.detail || "Login failed");
  }

  return response.json();
}

export async function getCurrentUser(sessionId) {
  const response = await fetch(`${Endpoints.CURRENT_USER}`, {
    headers: {
      ...sessionHeaders(sessionId),
    },
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error("Session invalid");
  }

  return response.json();
}


export function showAdminManagement() {
  window.location.href = '/backoffice';
}

export async function logout(sessionId) {
  await fetch(`${Endpoints.LOGOUT}`, {
    method: "POST",
    headers: {
      ...sessionHeaders(sessionId),
      ...csrfHeaders(sessionId),
    },
    credentials: "include",
  });
}