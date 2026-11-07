const API_BASE = ''

export async function api<T = any>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + path, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...opts?.headers,
    },
  })
  if (res.status === 401) {
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export function getToken(): string | null {
  return localStorage.getItem('favemus_token')
}

export function setToken(token: string) {
  localStorage.setItem('favemus_token', token)
}

export function clearToken() {
  localStorage.removeItem('favemus_token')
}

export function authHeaders(): HeadersInit {
  const token = getToken()
  if (token) return { Authorization: `Bearer ${token}` }
  return {}
}
