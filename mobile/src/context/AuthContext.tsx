import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import * as Notifications from 'expo-notifications';

import { api, getStoredToken, setStoredToken } from '../api';

type AuthState = {
  token: string | null;
  loading: boolean;
  email: string | null;
  score: number;
};

type AuthContextValue = AuthState & {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, timezone: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthContextValue | null>(null);

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

async function registerPushToken() {
  const { status } = await Notifications.requestPermissionsAsync();
  if (status !== 'granted') return;
  try {
    const token = await Notifications.getExpoPushTokenAsync().catch(() => null);
    const pushToken = token?.data;
    if (pushToken) await api.registerFcm(pushToken);
  } catch {
    // FCM / Expo project not configured — skip
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState<string | null>(null);
  const [score, setScore] = useState(0);

  const refresh = useCallback(async () => {
    if (!token) {
      setEmail(null);
      setScore(0);
      return;
    }
    const me = await api.me();
    setEmail(me.email);
    setScore(me.total_score);
  }, [token]);

  useEffect(() => {
    (async () => {
      const t = await getStoredToken();
      setToken(t);
      setLoading(false);
    })();
  }, []);

  useEffect(() => {
    if (!token) return;
    refresh().catch(() => {});
    registerPushToken().catch(() => {});
  }, [token, refresh]);

  const login = useCallback(async (emailIn: string, password: string) => {
    const r = await api.login(emailIn, password);
    await setStoredToken(r.access_token);
    setToken(r.access_token);
  }, []);

  const register = useCallback(async (emailIn: string, password: string, timezone: string) => {
    const r = await api.register(emailIn, password, timezone);
    await setStoredToken(r.access_token);
    setToken(r.access_token);
  }, []);

  const logout = useCallback(async () => {
    await setStoredToken(null);
    setToken(null);
  }, []);

  const value = useMemo(
    () => ({
      token,
      loading,
      email,
      score,
      login,
      register,
      logout,
      refresh,
    }),
    [token, loading, email, score, login, register, logout, refresh]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth outside AuthProvider');
  return v;
}
