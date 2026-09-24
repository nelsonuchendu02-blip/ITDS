import { NavLink } from 'react-router-dom'
import { NAV_ENTRIES } from '../../utils/navigation'
import { usePermission } from '../../hooks/usePermission'

function NavItem({ path, label }: { path: string; label: string }) {
  return (
    <NavLink to={path} end={path === '/'} className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}>
      {label}
    </NavLink>
  )
}

function GatedNavItem({ path, label, permission }: { path: string; label: string; permission: string }) {
  const allowed = usePermission(permission)
  if (!allowed) return null
  return <NavItem path={path} label={label} />
}

export function Sidebar({ open }: { open: boolean }) {
  return (
    <aside className={`sidebar${open ? ' is-open' : ''}`} aria-label="Primary navigation">
      <nav className="sidebar-nav">
        {NAV_ENTRIES.map((entry) => (
          <GatedNavItem key={entry.path} path={entry.path} label={entry.label} permission={entry.permission} />
        ))}
      </nav>
    </aside>
  )
}
