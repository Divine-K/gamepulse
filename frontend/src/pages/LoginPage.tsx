import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { Button } from '../components/ui/Button'
import { TextField } from '../components/ui/Field'
import { useAuth } from '../context/AuthContext'
import { AuthLayout } from '../layouts/AuthLayout'
import { ApiError } from '../services/api'

const schema = z.object({
  email: z.email('Enter a valid email address'),
  password: z.string().min(1, 'Enter your password'),
})
type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const { status, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const from = (location.state as { from?: string } | null)?.from ?? '/'
  if (status === 'authenticated') return <Navigate to={from} replace />

  const onSubmit = handleSubmit(async ({ email, password }) => {
    setFormError(null)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (error) {
      setFormError(
        error instanceof ApiError ? error.message : 'Something went wrong. Please try again.',
      )
    }
  })

  return (
    <AuthLayout title="Welcome back" subtitle="Log in to your GamePulse dashboard.">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@studio.dev"
          error={errors.email?.message}
          {...register('email')}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register('password')}
        />
        {formError && (
          <p
            role="alert"
            className="rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-sm text-danger"
          >
            {formError}
          </p>
        )}
        <Button type="submit" variant="primary" className="w-full" loading={isSubmitting}>
          Log in
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        New to GamePulse?{' '}
        <Link to="/register" className="font-medium text-accent-text hover:underline">
          Create an account
        </Link>
      </p>
    </AuthLayout>
  )
}
