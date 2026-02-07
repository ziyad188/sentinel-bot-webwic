import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Play, AlertTriangle, Camera, Users, Shield, LogOut } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/runs', label: 'Runs', icon: Play },
  { to: '/issues', label: 'Issues', icon: AlertTriangle },
  { to: '/evidence', label: 'Evidence', icon: Camera },
  { to: '/users', label: 'Users', icon: Users },
];

export function Sidebar({ onLogout }: { onLogout: () => void }) {
  return (
    <aside className="flex w-60 flex-col border-r border-border bg-card">
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-border">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
          <Shield className="h-4 w-4 text-primary-foreground" />
        </div>
        <span className="text-sm font-bold tracking-tight text-foreground">SentinelBot</span>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/dashboard'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border px-4 py-4 space-y-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="h-2 w-2 rounded-full bg-status-success" />
          Agent online
        </div>
        <Button variant="outline" size="sm" className="w-full justify-start gap-2" onClick={onLogout}>
          <LogOut className="h-4 w-4" />
          Log out
        </Button>
      </div>
    </aside>
  );
}
