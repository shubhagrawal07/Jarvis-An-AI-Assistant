import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

const TOKEN_KEY = 'jarvis_token';

export function getApiBase(): string {
  const extra = Constants.expoConfig?.extra as { apiUrl?: string } | undefined;
  return process.env.EXPO_PUBLIC_API_URL || extra?.apiUrl || 'http://localhost:8000';
}

export async function getStoredToken(): Promise<string | null> {
  return AsyncStorage.getItem(TOKEN_KEY);
}

export async function setStoredToken(token: string | null): Promise<void> {
  if (token) await AsyncStorage.setItem(TOKEN_KEY, token);
  else await AsyncStorage.removeItem(TOKEN_KEY);
}

async function request<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {}
): Promise<T> {
  const token = options.token ?? (await getStoredToken());
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const body = options.body;
  if (body && typeof body === 'string' && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(`${getApiBase()}${path}`, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    let msg = text || res.statusText;
    try {
      const j = JSON.parse(text) as { detail?: string | Array<{ msg?: string }> };
      if (typeof j.detail === 'string') msg = j.detail;
      else if (Array.isArray(j.detail) && j.detail[0]?.msg) msg = String(j.detail[0].msg);
    } catch {
      // use raw text
    }
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export type Task = {
  id: string;
  title: string;
  task_type: string;
  due_at: string;
  priority: string;
  reminder_at: string | null;
  points: number;
  penalty_text: string;
  status: string;
  completed_at: string | null;
  google_event_id: string | null;
};

export const api = {
  register: (email: string, password: string, timezone: string) =>
    request<{ access_token: string }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, timezone }),
      token: null,
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
      token: null,
    }),
  me: () => request<{ id: string; email: string; total_score: number; timezone: string }>('/users/me'),
  tasksToday: () => request<Task[]>('/tasks?today=true'),
  completeTask: (id: string) =>
    request<Task>(`/tasks/${id}/complete`, { method: 'POST' }),
  commandText: (text: string) =>
    request<{ action: string; message: string; task_ids: string[] }>('/command/text', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  closeDay: (local_date: string, notes?: string) =>
    request<unknown>('/day/close', {
      method: 'POST',
      body: JSON.stringify({ local_date, notes: notes ?? null }),
    }),
  registerFcm: (token: string) =>
    request<{ ok: boolean }>('/users/me/fcm', {
      method: 'PATCH',
      body: JSON.stringify({ token }),
    }),
  googleAuthUrl: () =>
    request<{ authorization_url: string }>('/auth/google/authorize-url'),
  commandVoice: async (uri: string) => {
    const token = await getStoredToken();
    const form = new FormData();
    form.append(
      'audio',
      { uri, name: 'voice.m4a', type: 'audio/m4a' } as unknown as Blob
    );
    const res = await fetch(`${getApiBase()}/command/voice`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{ action: string; message: string; task_ids: string[] }>;
  },
};
