import { useEffect, useState } from 'react';

import { userApi } from '../services/userApi';
import { clearAccessToken, getAuthSession, saveUserProfile } from '../utils/auth';

export function useAuthSession() {
  const [session, setSession] = useState(() => getAuthSession());

  useEffect(() => {
    const syncSession = () => {
      setSession(getAuthSession());
    };

    window.addEventListener('storage', syncSession);
    window.addEventListener('authchange', syncSession);

    return () => {
      window.removeEventListener('storage', syncSession);
      window.removeEventListener('authchange', syncSession);
    };
  }, []);

  useEffect(() => {
    let active = true;

    async function hydrateProfile() {
      if (!session.token) {
        return;
      }

      if (session.profile?.id === session.userId) {
        return;
      }

      try {
        const profile = await userApi.getProfile();
        saveUserProfile(profile);
        if (active) {
          setSession(getAuthSession());
        }
      } catch (error) {
        if (error?.response?.status === 401) {
          clearAccessToken();
        }
      }
    }

    hydrateProfile();
    return () => {
      active = false;
    };
  }, [session.profile?.id, session.token, session.userId]);

  const updateProfile = async (payload) => {
    const profile = await userApi.updateProfile(payload);
    saveUserProfile(profile);
    setSession(getAuthSession());
    return profile;
  };

  return {
    session,
    logout: clearAccessToken,
    updateProfile,
  };
}
