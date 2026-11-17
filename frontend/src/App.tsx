import { MotionConfig } from 'motion/react'
import { lazy, Suspense } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { Skeleton } from './components/ui/Skeleton'
import { GameProvider } from './context/GameContext'
import { useAuth } from './context/AuthContext'
import { AppShell } from './layouts/AppShell'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'

// Each page is its own chunk, so the first load only downloads what the visitor needs.
const OverviewPage = lazy(() =>
  import('./pages/OverviewPage').then((m) => ({ default: m.OverviewPage })),
)
const GamesPage = lazy(() => import('./pages/GamesPage').then((m) => ({ default: m.GamesPage })))
const GameDetailPage = lazy(() =>
  import('./pages/GameDetailPage').then((m) => ({ default: m.GameDetailPage })),
)
const PlayersPage = lazy(() =>
  import('./pages/PlayersPage').then((m) => ({ default: m.PlayersPage })),
)
const PlayerPage = lazy(() => import('./pages/PlayerPage').then((m) => ({ default: m.PlayerPage })))
const SessionsPage = lazy(() =>
  import('./pages/SessionsPage').then((m) => ({ default: m.SessionsPage })),
)
const LeaderboardsPage = lazy(() =>
  import('./pages/LeaderboardsPage').then((m) => ({ default: m.LeaderboardsPage })),
)
const AchievementsPage = lazy(() =>
  import('./pages/AchievementsPage').then((m) => ({ default: m.AchievementsPage })),
)
const AnalyticsPage = lazy(() =>
  import('./pages/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })),
)
const LiveEventsPage = lazy(() =>
  import('./pages/LiveEventsPage').then((m) => ({ default: m.LiveEventsPage })),
)
const SettingsPage = lazy(() =>
  import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })),
)
const DesignSystemPage = lazy(() =>
  import('./pages/DesignSystemPage').then((m) => ({ default: m.DesignSystemPage })),
)
const ComingSoonPage = lazy(() =>
  import('./pages/ComingSoonPage').then((m) => ({ default: m.ComingSoonPage })),
)
const NotFoundPage = lazy(() =>
  import('./pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage })),
)

function PageFallback() {
  return (
    <div aria-busy="true" aria-label="Loading page" className="space-y-4">
      <Skeleton className="h-9 w-56" />
      <Skeleton className="h-40 w-full" />
    </div>
  )
}

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

function Page({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<PageFallback />}>{children}</Suspense>
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
            <Route
              index
              element={
                <Page>
                  <OverviewPage />
                </Page>
              }
            />
            <Route
              path="games"
              element={
                <Page>
                  <GamesPage />
                </Page>
              }
            />
            <Route
              path="games/:gameId"
              element={
                <Page>
                  <GameDetailPage />
                </Page>
              }
            />
            <Route
              path="players"
              element={
                <Page>
                  <PlayersPage />
                </Page>
              }
            />
            <Route
              path="players/:playerId"
              element={
                <Page>
                  <PlayerPage />
                </Page>
              }
            />
            <Route
              path="sessions"
              element={
                <Page>
                  <SessionsPage />
                </Page>
              }
            />
            <Route
              path="leaderboards"
              element={
                <Page>
                  <LeaderboardsPage />
                </Page>
              }
            />
            <Route
              path="achievements"
              element={
                <Page>
                  <AchievementsPage />
                </Page>
              }
            />
            <Route
              path="analytics"
              element={
                <Page>
                  <AnalyticsPage />
                </Page>
              }
            />
            <Route
              path="live"
              element={
                <Page>
                  <LiveEventsPage />
                </Page>
              }
            />
            <Route
              path="settings"
              element={
                <Page>
                  <SettingsPage />
                </Page>
              }
            />
            <Route
              path="design"
              element={
                <Page>
                  <DesignSystemPage />
                </Page>
              }
            />
            {['playground', 'docs'].map((path) => (
              <Route
                key={path}
                path={path}
                element={
                  <Page>
                    <ComingSoonPage />
                  </Page>
                }
              />
            ))}
            <Route
              path="*"
              element={
                <Page>
                  <NotFoundPage />
                </Page>
              }
            />
          </Route>
        </Route>
      </Routes>
    </MotionConfig>
  )
}
