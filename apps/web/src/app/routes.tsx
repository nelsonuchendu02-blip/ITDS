import type { RouteObject } from 'react-router-dom'
import { AppLayout } from '../components/layout/AppLayout'
import { ProtectedRoute } from './ProtectedRoute'
import { Login } from '../pages/Login'
import { Dashboard } from '../pages/Dashboard'
import { Devices } from '../pages/Devices'
import { Monitoring } from '../pages/Monitoring'
import { Agents } from '../pages/Agents'
import { Incidents } from '../pages/Incidents'
import { Discovery } from '../pages/Discovery'
import { Diagnostics } from '../pages/Diagnostics'
import { RootCause } from '../pages/RootCause'
import { Recommendations } from '../pages/Recommendations'
import { Remediation } from '../pages/Remediation'
import { Networks } from '../pages/Networks'
import { Audit } from '../pages/Audit'
import { NotFound } from '../pages/NotFound'

export const routes: RouteObject[] = [
  { path: '/login', element: <Login /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: '/', element: <Dashboard /> },
          { path: '/devices', element: <Devices /> },
          { path: '/monitoring', element: <Monitoring /> },
          { path: '/agents', element: <Agents /> },
          { path: '/incidents', element: <Incidents /> },
          { path: '/discovery', element: <Discovery /> },
          { path: '/diagnostics', element: <Diagnostics /> },
          { path: '/root-cause', element: <RootCause /> },
          { path: '/recommendations', element: <Recommendations /> },
          { path: '/remediation', element: <Remediation /> },
          { path: '/networks', element: <Networks /> },
          { path: '/audit', element: <Audit /> },
          { path: '*', element: <NotFound /> },
        ],
      },
    ],
  },
]
