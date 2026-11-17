import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { LogOut, Moon, Sun } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { TextField } from '../components/ui/Field'
import { PageHeader } from '../components/ui/PageHeader'
import { useToast } from '../components/ui/Toast'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { cn } from '../lib/cn'
import { ApiError } from '../services/api'
import { authApi } from '../services/endpoints'

const profileSchema = z.object({ display_name: z.string().trim().min(1, 'Enter a name').max(100) })
const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password'),
    new_password: z.string().min(8, 'Use at least 8 characters').max(128),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, {
    path: ['confirm'],
    message: 'Passwords do not match',
  })

export function SettingsPage() {
  const { user, logout, updateUser } = useAuth()
  const { theme, setTheme } = useTheme()
  const toast = useToast()

  const profile = useForm({
    resolver: zodResolver(profileSchema),
    values: { display_name: user?.display_name ?? '' },
  })
  const saveProfile = useMutation({
    mutationFn: (v: z.infer<typeof profileSchema>) =>
      authApi.updateMe({ display_name: v.display_name }),
    onSuccess: (updated) => {
      updateUser(updated)
      toast.success('Profile updated')
    },
    onError: (e) =>
      toast.error(
        'Could not update your profile',
        e instanceof ApiError ? e.message : 'Try again.',
      ),
  })

  const password = useForm({ resolver: zodResolver(passwordSchema) })
  const changePassword = useMutation({
    mutationFn: (v: z.infer<typeof passwordSchema>) =>
      authApi.updateMe({ current_password: v.current_password, new_password: v.new_password }),
    onSuccess: () => {
      password.reset()
      toast.success('Password changed', 'Use the new password next time you log in.')
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 403)
        password.setError('current_password', { message: 'Current password is incorrect' })
      else
        toast.error(
          'Could not change your password',
          e instanceof ApiError ? e.message : 'Try again.',
        )
    },
  })

  return (
    <>
      <PageHeader title="Settings" description="Your profile, password and appearance." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Profile" description={user?.email} />
          <CardBody>
            <form
              onSubmit={profile.handleSubmit((v) => saveProfile.mutate(v))}
              noValidate
              className="space-y-4"
            >
              <TextField
                label="Display name"
                error={profile.formState.errors.display_name?.message}
                {...profile.register('display_name')}
              />
              <Button
                type="submit"
                variant="primary"
                loading={saveProfile.isPending}
                disabled={!profile.formState.isDirty}
              >
                Save
              </Button>
            </form>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Change password" />
          <CardBody>
            <form
              onSubmit={password.handleSubmit((v) => changePassword.mutate(v))}
              noValidate
              className="space-y-4"
            >
              <TextField
                label="Current password"
                type="password"
                autoComplete="current-password"
                error={password.formState.errors.current_password?.message}
                {...password.register('current_password')}
              />
              <TextField
                label="New password"
                type="password"
                autoComplete="new-password"
                hint="At least 8 characters."
                error={password.formState.errors.new_password?.message}
                {...password.register('new_password')}
              />
              <TextField
                label="Confirm new password"
                type="password"
                autoComplete="new-password"
                error={password.formState.errors.confirm?.message}
                {...password.register('confirm')}
              />
              <Button type="submit" variant="primary" loading={changePassword.isPending}>
                Change password
              </Button>
            </form>
          </CardBody>
        </Card>

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
                  className={cn(
                    'flex items-center gap-2 rounded-md border px-4 py-3 text-sm font-medium transition-colors',
                    theme === value
                      ? 'border-accent bg-accent-soft text-accent-text'
                      : 'border-line text-muted hover:border-line-strong hover:text-fg',
                  )}
                >
                  <Icon aria-hidden className="size-4" /> {label}
                </button>
              ))}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Session"
            description={`Signed in as ${user?.display_name} (${user?.role}).`}
          />
          <CardBody>
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
