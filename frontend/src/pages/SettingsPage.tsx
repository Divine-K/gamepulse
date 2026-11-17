import { LogOut, Moon, Sun } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'

export function SettingsPage() {
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  return (
    <>
      <PageHeader title="Settings" description="Appearance and account." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Appearance"
            description="Dark is the default. Your choice is saved in this browser."
          />
          <CardBody>
            <div role="radiogroup" aria-label="Theme" className="grid grid-cols-2 gap-3">
              {(
                [
                  ['dark', 'Dark', Moon],
                  ['light', 'Light', Sun],
                ] as const
              ).map(([value, label, Icon]) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={theme === value}
                  onClick={() => setTheme(value)}
                  className={`flex items-center gap-2 rounded-md border px-4 py-3 text-sm font-medium transition-colors ${
                    theme === value
                      ? 'border-accent bg-accent-soft text-accent-text'
                      : 'border-line text-muted hover:border-line-strong hover:text-fg'
                  }`}
                >
                  <Icon aria-hidden className="size-4" /> {label}
                </button>
              ))}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Account" />
          <CardBody className="space-y-4">
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Name</dt>
                <dd>{user?.display_name}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Email</dt>
                <dd>{user?.email}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Role</dt>
                <dd className="capitalize">{user?.role}</dd>
              </div>
            </dl>
            <Button
              variant="danger"
              icon={<LogOut aria-hidden className="size-4" />}
              onClick={logout}
            >
              Log out
            </Button>
          </CardBody>
        </Card>
      </div>
    </>
  )
}
