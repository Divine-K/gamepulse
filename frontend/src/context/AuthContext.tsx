import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { setUnauthorizedHandler, tokenStore } from '../services/api'
import { authApi } from '../services/endpoints'
import type { Developer } from '../types/api'

type Status = 'loading' | 'authenticated' | 'anonymous'

interface AuthValue {
  status: Status
  user: Developer | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<{ status: Status; user: Developer | null }>({
    status: tokenStore.get() ? 'loading' : 'anonymous',
    user: null,
  })

  const signOut = useCallback(() => {
    tokenStore.clear()
    queryClient.clear()
    setState({ status: 'anonymous', user: null })
  }, [queryClient])

  // Restore the session after a page refresh.
  useEffect(() => {
    if (!tokenStore.get()) return
    const controller = new AbortController()
    authApi
      .me(controller.signal)
      .then((user) => setState({ status: 'authenticated', user }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        tokenStore.clear()
        setState({ status: 'anonymous', user: null })
      })
    return () => controller.abort()
  }, [])

  // Any 401 on an authenticated request (e.g. expired token) signs the user out.
  useEffect(() => {
    setUnauthorizedHandler(signOut)
    return () => setUnauthorizedHandler(null)
  }, [signOut])

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await authApi.login({ email, password })
    tokenStore.set(access_token)
    const user = await authApi.me()
    setState({ status: 'authenticated', user })
  }, [])

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      await authApi.register({ email, password, display_name: displayName })
      await login(email, password)
    },
    [login],
  )

  const value = useMemo<AuthValue>(
    () => ({ ...state, login, register, logout: signOut }),
    [state, login, register, signOut],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
