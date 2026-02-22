const CSRF_COOKIE_PREFIX = "chat_csrf_token";

export function getCookie(name) {
  const cookieValue = `; ${document.cookie}`;
  const parts = cookieValue.split(`; ${name}=`);
  if (parts.length !== 2) {
    return null;
  }
  return parts.pop().split(";").shift();
}

export function csrfHeaders(sessionId) {
  const token = getCookie(`${CSRF_COOKIE_PREFIX}_${sessionId}`);
  return token ? { "X-CSRF-Token": token } : {};
}

export function sessionHeaders(sessionId) {
  return { "X-Session-Id": sessionId };
}