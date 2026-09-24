import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Login } from './Login'

const mockUseAuth = vi.fn()

vi.mock('../app/providers/AuthProvider', () => ({
  useAuth: () => mockUseAuth(),
}))

describe('Login', () => {
  it('submits entered credentials to login()', async () => {
    const login = vi.fn(async () => {})
    mockUseAuth.mockReturnValue({ status: 'idle', error: null, login })

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'operator@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'hunter22' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(login).toHaveBeenCalledWith('operator@example.com', 'hunter22')
  })

  it('shows an authenticating state and disables the submit button while signing in', () => {
    mockUseAuth.mockReturnValue({ status: 'authenticating', error: null, login: vi.fn() })

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    )

    const button = screen.getByRole('button', { name: 'Signing in…' })
    expect(button).toBeDisabled()
  })

  it('surfaces a login error from the auth context', () => {
    mockUseAuth.mockReturnValue({ status: 'error', error: 'Invalid credentials', login: vi.fn() })

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials')
  })

  it('redirects to the originally requested route once authenticated', () => {
    mockUseAuth.mockReturnValue({ status: 'authenticated', error: null, login: vi.fn() })

    render(
      <MemoryRouter initialEntries={[{ pathname: '/login', state: { from: { pathname: '/incidents', search: '', hash: '' } } }]}>
        <Login />
      </MemoryRouter>,
    )

    expect(screen.queryByRole('button', { name: 'Sign in' })).not.toBeInTheDocument()
  })
})
