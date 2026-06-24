import { apiRequest } from '#/lib/api'

export type AuthUser = {
  id: number
  email: string
  display_name: string | null
  avatar_url: string | null
}

export type TokenResponse = {
  access_token: string
  token_type: string
  user: AuthUser
}

export const authApi = {
  register: (email: string, password: string) =>
    apiRequest<TokenResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    apiRequest<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  google: (credential: string) =>
    apiRequest<TokenResponse>('/auth/google', {
      method: 'POST',
      body: JSON.stringify({ credential }),
    }),
  me: () => apiRequest<AuthUser>('/auth/me'),
}
