import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './providers/AuthProvider'

export function ProtectedRoute() {
  const { status } = useAuth()
  const location = useLocation()

  if (status !== 'authenticated') {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <Outlet />
}
