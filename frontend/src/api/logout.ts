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


export async function summary(sessionId) {
  return fetch(`${Endpoints.SUMMARY}`, {
    method: "POST",
    headers: {
      ...sessionHeaders(sessionId),
      ...csrfHeaders(sessionId),
    },
    credentials: "include",
  });
}