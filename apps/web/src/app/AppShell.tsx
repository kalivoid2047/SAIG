import { NavLink, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  permission?: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: "▣" },
  { to: "/farmers", label: "Farmers", icon: "❋", permission: "farmers:read" },
  { to: "/map", label: "Map", icon: "▦", permission: "farms:read" },
  { to: "/disease-reports", label: "Disease reports", icon: "⚠", permission: "crops:read" },
  { to: "/inventory", label: "Inventory", icon: "▤", permission: "inventory:read" },
  { to: "/varieties", label: "Varieties", icon: "🌱", permission: "varieties:read" },
  { to: "/admin/regions", label: "Regions", icon: "◫", permission: "regions:manage" },
  { to: "/admin/users", label: "Users", icon: "◉", permission: "users:read" },
  { to: "/admin/roles", label: "Roles", icon: "⛨", permission: "roles:manage" },
  { to: "/admin/departments", label: "Departments", icon: "◈", permission: "org:manage" },
  { to: "/admin/audit", label: "Audit log", icon: "≣", permission: "audit:read" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { user, hasPermission, logout } = useAuth();
  const navigate = useNavigate();

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.permission || hasPermission(item.permission),
  );

  return (
    <div className="flex h-screen">
      <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-card">
        <div className="flex items-center gap-2 px-4 py-5">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary font-bold text-primary-foreground">
            S
          </span>
          <div>
            <p className="text-sm font-semibold leading-tight">SAIG</p>
            <p className="text-[10px] text-muted">Agro Intelligence Grid</p>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 px-2" aria-label="Main navigation">
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                [
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-muted hover:bg-elevated hover:text-foreground",
                ].join(" ")
              }
            >
              <span aria-hidden>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-border p-3">
          <p className="truncate text-sm font-medium">{user?.fullName}</p>
          <p className="truncate text-xs text-muted">{user?.email}</p>
          <Button
            variant="secondary"
            className="mt-3 w-full justify-center"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
          >
            Sign out
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto px-8 py-6">{children}</main>
    </div>
  );
}
