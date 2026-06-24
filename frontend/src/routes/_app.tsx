import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'
import { AUTH_TOKEN_KEY } from '#/lib/auth-token'

export const Route = createFileRoute('/_app')({
  beforeLoad: ({ location }) => {
    if (typeof window === 'undefined') return
    if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
      throw redirect({
        to: '/login',
        search: { redirect: location.href },
      })
    }
  },
  component: () => <Outlet />,
})
