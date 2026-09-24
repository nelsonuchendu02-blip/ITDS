import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { HealthFooter } from './HealthFooter'

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="app-shell">
      <Sidebar open={sidebarOpen} />
      <div className="app-main">
        <Topbar onToggleSidebar={() => setSidebarOpen((open) => !open)} />
        <main className="app-content" id="main-content">
          <Outlet />
        </main>
        <HealthFooter />
      </div>
    </div>
  )
}
