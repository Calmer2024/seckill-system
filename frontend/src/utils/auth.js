const ACCESS_TOKEN_KEY = 'access_token';

function decodeBase64Url(value) {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
  return atob(padded);
}

export function parseJwt(token) {
  if (!token) {
    return null;
  }

  try {
    const [, payload] = token.split('.');
    if (!payload) {
      return null;
    }
    return JSON.parse(decodeBase64Url(payload));
  } catch {
    return null;
  }
}

export function getStoredToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getAuthSession() {
  const token = getStoredToken();
  const payload = parseJwt(token);
  const username = payload?.username ?? null;
  const userId = payload?.sub ? Number(payload.sub) : null;

  return {
    token,
    username,
    userId,
    isAuthenticated: Boolean(token && username),
  };
}

export function saveAccessToken(token) {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
  window.dispatchEvent(new Event('authchange'));
}

export function clearAccessToken() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.dispatchEvent(new Event('authchange'));
}
