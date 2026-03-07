import { csrfHeaders, sessionHeaders } from "../utils/authUtils";
import { Endpoints } from "./endpoints";

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


export function summary(sessionId) {
  fetch(`${Endpoints.SUMMARY}`, {
    method: "POST",
    headers: {
      ...sessionHeaders(sessionId),
      ...csrfHeaders(sessionId),
    },
    credentials: "include",
  });
}