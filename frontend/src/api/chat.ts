import { csrfHeaders, sessionHeaders } from "../utils/authUtils";
import { Endpoints } from "./endpoints";

export async function sendChatMessage(message, sessionId) {
  const response = await fetch(`${Endpoints.CHAT}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...sessionHeaders(sessionId),
      ...csrfHeaders(sessionId),
    },
    credentials: "include",
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Chat error" }));
    throw new Error(err.detail || "Chat error");
  }

  return response.json();
}

export async function getMessages(sessionId) {
  const response = await fetch(`${Endpoints.GET_MESSAGES(sessionId)}`, {
    method: "GET",
    headers: {
      ...sessionHeaders(sessionId),
      ...csrfHeaders(sessionId),
    },
    credentials: "include",
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Chat error" }));
    throw new Error(err.detail || "Chat error");
  }
  return response.json();
}
