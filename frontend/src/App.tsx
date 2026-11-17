import { MotionConfig } from 'motion/react'
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { Skeleton } from './components/ui/Skeleton'
import { GameProvider } from './context/GameContext'
import { useAuth } from './context/AuthContext'
import { AppShell } from './layouts/AppShell'
import { ComingSoonPage } from './pages/ComingSoonPage'
import { DesignSystemPage } from './pages/DesignSystemPage'
import { GamesPage } from './pages/GamesPage'
import { LiveEventsPage } from './pages/LiveEventsPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { OverviewPage } from './pages/OverviewPage'
import { RegisterPage } from './pages/RegisterPage'
import { SettingsPage } from './pages/SettingsPage'

/** Redirects anonymous visitors to the login page, remembering where they were going. */
function ProtectedRoute() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') {
    return (
      <div
        aria-busy="true"
        aria-label="Loading"
        className="flex min-h-dvh items-center justify-center"
      >
        <Skeleton className="h-10 w-48" />
      </div>
    )
  }
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return (
    <GameProvider>
      <Outlet />
    </GameProvider>
  )
}

export default function App() {
  return (
    // reducedMotion="user": every Motion animation respects the OS "reduce motion" setting.
    <MotionConfig reducedMotion="user">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route index element={<OverviewPage />} />
            <Route path="games" element={<GamesPage />} />
            <Route path="live" element={<LiveEventsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="design" element={<DesignSystemPage />} />
            {[
              'players',
              'sessions',
              'leaderboards',
              'achievements',
              'analytics',
              'playground',
              'docs',
            ].map((path) => (
              <Route key={path} path={path} element={<ComingSoonPage />} />
            ))}
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
      </Routes>
    </MotionConfig>
  )
}
