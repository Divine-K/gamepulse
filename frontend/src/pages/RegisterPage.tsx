import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { Button } from '../components/ui/Button'
import { TextField } from '../components/ui/Field'
import { useAuth } from '../context/AuthContext'
import { AuthLayout } from '../layouts/AuthLayout'
import { ApiError } from '../services/api'

const schema = z.object({
  display_name: z.string().trim().min(1, 'Tell us what to call you').max(100),
  email: z.email('Enter a valid email address'),
  password: z.string().min(8, 'Use at least 8 characters').max(128),
})
type FormValues = z.infer<typeof schema>

export function RegisterPage() {
  const { status, register: registerAccount } = useAuth()
  const navigate = useNavigate()
  const [formError, setFormError] = useState<string | null>(null)
  // Once registration succeeds the auth state flips to "authenticated" before navigate() runs;
  // remember why, so a brand-new developer lands on Games instead of being bounced to Overview.
  const [justRegistered, setJustRegistered] = useState(false)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  if (status === 'authenticated') return <Navigate to={justRegistered ? '/games' : '/'} replace />

  const onSubmit = handleSubmit(async ({ email, password, display_name }) => {
    setFormError(null)
    try {
      setJustRegistered(true)
      await registerAccount(email, password, display_name)
      navigate('/games', { replace: true })
    } catch (error) {
      setJustRegistered(false)
      if (error instanceof ApiError && error.code === 'email_taken') {
        setError('email', { message: 'An account with this email already exists' })
      } else if (error instanceof ApiError && error.status === 429) {
        setFormError('Too many attempts. Wait a minute and try again.')
      } else {
        setFormError(
          error instanceof ApiError ? error.message : 'Something went wrong. Please try again.',
        )
      }
    }
  })

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Free to use. Connect your first game in minutes."
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <TextField
          label="Name"
          autoComplete="name"
          placeholder="Ada Lovelace"
          error={errors.display_name?.message}
          {...register('display_name')}
        />
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
          autoComplete="new-password"
          hint="At least 8 characters."
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
          Create account
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-accent-text hover:underline">
          Log in
        </Link>
      </p>
    </AuthLayout>
  )
}
