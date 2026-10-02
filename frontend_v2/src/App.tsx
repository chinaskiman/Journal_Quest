import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { LoadingState } from './components/states'

// Larger routes are lazy-loaded to keep the initial bundle small.
const QuestHubPage = lazy(() => import('./pages/QuestHubPage'))
const TradesPage = lazy(() => import('./pages/TradesPage'))
const TradeDetailPage = lazy(() => import('./pages/TradeDetailPage'))
const QuickCapturePage = lazy(() => import('./pages/QuickCapturePage'))
const QuickReviewPage = lazy(() => import('./pages/QuickReviewPage'))
const DeepReviewPage = lazy(() => import('./pages/DeepReviewPage'))
const EmotionalPage = lazy(() => import('./pages/EmotionalPage'))
const DailyReviewPage = lazy(() => import('./pages/DailyReviewPage'))
const WeeklyReviewPage = lazy(() => import('./pages/WeeklyReviewPage'))
const QuestCenterPage = lazy(() => import('./pages/QuestCenterPage'))
const AchievementsPage = lazy(() => import('./pages/AchievementsPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))

function NotFoundPage() {
  return (
    <section className="panel">
      <h1>Unknown route</h1>
      <p className="muted">
        That page does not exist. Use the navigation on the left to continue journaling.
      </p>
    </section>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route
          path="/"
          element={
            <Suspense fallback={<LoadingState />}>
              <QuestHubPage />
            </Suspense>
          }
        />
        <Route
          path="/trades"
          element={
            <Suspense fallback={<LoadingState />}>
              <TradesPage />
            </Suspense>
          }
        />
        <Route
          path="/trades/:id"
          element={
            <Suspense fallback={<LoadingState />}>
              <TradeDetailPage />
            </Suspense>
          }
        />
        <Route
          path="/quick-capture"
          element={
            <Suspense fallback={<LoadingState />}>
              <QuickCapturePage />
            </Suspense>
          }
        />
        <Route
          path="/quick-review"
          element={
            <Suspense fallback={<LoadingState />}>
              <QuickReviewPage />
            </Suspense>
          }
        />
        <Route
          path="/deep-review"
          element={
            <Suspense fallback={<LoadingState />}>
              <DeepReviewPage />
            </Suspense>
          }
        />
        <Route
          path="/emotional"
          element={
            <Suspense fallback={<LoadingState />}>
              <EmotionalPage />
            </Suspense>
          }
        />
        <Route
          path="/daily-review"
          element={
            <Suspense fallback={<LoadingState />}>
              <DailyReviewPage />
            </Suspense>
          }
        />
        <Route
          path="/weekly-review"
          element={
            <Suspense fallback={<LoadingState />}>
              <WeeklyReviewPage />
            </Suspense>
          }
        />
        <Route
          path="/quests"
          element={
            <Suspense fallback={<LoadingState />}>
              <QuestCenterPage />
            </Suspense>
          }
        />
        <Route
          path="/achievements"
          element={
            <Suspense fallback={<LoadingState />}>
              <AchievementsPage />
            </Suspense>
          }
        />
        <Route
          path="/settings"
          element={
            <Suspense fallback={<LoadingState />}>
              <SettingsPage />
            </Suspense>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
