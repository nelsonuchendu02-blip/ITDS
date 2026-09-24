import { useRoutes } from 'react-router-dom'
import { AuthProvider } from './app/providers/AuthProvider'
import { routes } from './app/routes'

function AppRoutes() {
  return useRoutes(routes)
}

function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}

export default App
