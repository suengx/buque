import {
  HeadContent,
  Outlet,
  Scripts,
  createRootRouteWithContext,
  useRouterState,
} from '@tanstack/react-router'
import { TanStackRouterDevtoolsPanel } from '@tanstack/react-router-devtools'
import { TanStackDevtools } from '@tanstack/react-devtools'
import { AuthProvider } from '../context/AuthContext'
import { SnapshotProvider } from '../context/SnapshotContext'
import AppSidebar from '../components/buque/AppSidebar'
import { ContextDock } from '../components/buque/ContextDock'
import TanStackQueryDevtools from '../integrations/tanstack-query/devtools'
import appCss from '../styles.css?url'
import type { QueryClient } from '@tanstack/react-query'

interface MyRouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<MyRouterContext>()({
  head: () => ({
    meta: [
      { charSet: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      { title: '补雀 BuQue' },
    ],
    links: [{ rel: 'stylesheet', href: appCss }],
  }),
  shellComponent: RootDocument,
})

function RootDocument() {
  return (
    <html lang="zh-CN" data-theme="light" suppressHydrationWarning>
      <head>
        <HeadContent />
      </head>
      <body className="font-sans antialiased">
        <AuthProvider>
          <AppShell />
        </AuthProvider>
        <TanStackDevtools
          config={{ position: 'bottom-right' }}
          plugins={[
            { name: 'Tanstack Router', render: <TanStackRouterDevtoolsPanel /> },
            TanStackQueryDevtools,
          ]}
        />
        <Scripts />
      </body>
    </html>
  )
}

function AppShell() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const isLogin = pathname === '/login' || pathname.startsWith('/login/')

  if (isLogin) {
    return <Outlet />
  }

  return (
    <SnapshotProvider>
      <AppSidebar />
      <main className="min-h-screen pl-60">
        <ContextDock />
        <div className="px-6 py-5">
          <div className="page-content">
            <Outlet />
          </div>
        </div>
      </main>
    </SnapshotProvider>
  )
}
