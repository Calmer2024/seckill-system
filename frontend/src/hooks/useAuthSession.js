import { useEffect, useState } from 'react';

import { clearAccessToken, getAuthSession } from '../utils/auth';

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

  return {
    session,
    logout: clearAccessToken,
  };
}
