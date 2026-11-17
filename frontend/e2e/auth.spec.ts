import { API, PASSWORD, createAccount, expect, test } from './fixtures'

test('protected pages send visitors to the login page and back again', async ({
  page,
  request,
}) => {
  await page.goto('/players')
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()

  const account = await createAccount(request)
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page).toHaveURL(/\/players$/) // returned to where they were going
})

test('wrong credentials show one generic message', async ({ page, request }) => {
  const account = await createAccount(request)
  await page.goto('/login')
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill('wrong-password')
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('alert')).toHaveText('Incorrect email or password.')
  await page.getByLabel('Email').fill('nobody@example.com')
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('alert')).toHaveText('Incorrect email or password.') // same message: no account enumeration
})

test('form validation explains problems before calling the server', async ({ page }) => {
  await page.goto('/register')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByText('Enter a valid email address')).toBeVisible()
  await expect(page.getByText('Use at least 8 characters')).toBeVisible()
})

test('registering an existing email is reported on the email field', async ({ page, request }) => {
  const account = await createAccount(request)
  await page.goto('/register')
  await page.getByLabel('Name').fill('Dup')
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByText('An account with this email already exists')).toBeVisible()
})

test('logging out ends the session; a forged token is rejected', async ({ page, request }) => {
  const account = await createAccount(request)
  await page.goto('/login')
  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible()

  await page.getByRole('button', { name: 'Account menu' }).click()
  await page.getByRole('menuitem', { name: 'Log out' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto('/')
  await expect(page).toHaveURL(/\/login$/) // really signed out

  await page.evaluate(() => sessionStorage.setItem('gp-token', 'forged.token.value'))
  await page.goto('/')
  await expect(page).toHaveURL(/\/login$/)
  expect(await page.evaluate(() => sessionStorage.getItem('gp-token'))).toBeNull() // cleared
})

test('changing the password signs the user out and invalidates a copied token', async ({
  page,
  request,
}) => {
  const account = await createAccount(request)
  await page.addInitScript(
    (token) => sessionStorage.getItem('gp-token') ?? sessionStorage.setItem('gp-token', token),
    account.token,
  )
  await page.goto('/settings')
  await page.getByLabel('Current password').fill(PASSWORD)
  await page.getByLabel('New password', { exact: true }).fill('a-brand-new-password')
  await page.getByLabel('Confirm new password').fill('a-brand-new-password')
  await new Promise((resolve) => setTimeout(resolve, 1100)) // tokens carry whole-second timestamps
  await page.getByRole('button', { name: 'Change password' }).click()

  await expect(page).toHaveURL(/\/login$/)
  // The token someone might have copied earlier no longer works.
  const stolen = await request.get(`${API}/api/v1/developers/me`, {
    headers: { Authorization: `Bearer ${account.token}` },
  })
  expect(stolen.status()).toBe(401)

  await page.getByLabel('Email').fill(account.email)
  await page.getByLabel('Password').fill('a-brand-new-password')
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible()
})
