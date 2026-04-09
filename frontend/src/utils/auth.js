const ACCESS_TOKEN_KEY = 'access_token';
const USER_PROFILE_KEY = 'user_profile';

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

export function getStoredProfile() {
  const raw = localStorage.getItem(USER_PROFILE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function getAuthSession() {
  const token = getStoredToken();
  const payload = parseJwt(token);
  const profile = getStoredProfile();
  const username = profile?.username ?? payload?.username ?? null;
  const userId = payload?.sub ? Number(payload.sub) : null;

  return {
    token,
    username,
    userId,
    avatarUrl: profile?.avatar_url ?? '/avatar.JPG',
    createdAt: profile?.created_at ?? null,
    profile,
    isAuthenticated: Boolean(token && username),
  };
}

export function saveAccessToken(token) {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
  localStorage.removeItem(USER_PROFILE_KEY);
  window.dispatchEvent(new Event('authchange'));
}

export function saveUserProfile(profile) {
  localStorage.setItem(USER_PROFILE_KEY, JSON.stringify(profile));
  window.dispatchEvent(new Event('authchange'));
}

export function clearAccessToken() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(USER_PROFILE_KEY);
  window.dispatchEvent(new Event('authchange'));
}
