import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Department, Organization, Page, Role, User } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { Badge, Card, PageHeader } from "@/components/ui";

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <Card>
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p>
    </Card>
  );
}

export function HomePage() {
  const { user, permissions, hasPermission } = useAuth();

  const org = useQuery({
    queryKey: ["organization"],
    queryFn: () => api<Organization>("/api/v1/organization"),
  });
  const users = useQuery({
    queryKey: ["users", "count"],
    queryFn: () => api<Page<User>>("/api/v1/users", { params: { pageSize: 1 } }),
    enabled: hasPermission("users:read"),
  });
  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () => api<Role[]>("/api/v1/roles"),
    enabled: hasPermission("users:read"),
  });
  const departments = useQuery({
    queryKey: ["departments"],
    queryFn: () => api<Department[]>("/api/v1/departments"),
  });

  return (
    <div>
      <PageHeader
        title={`Welcome, ${user?.fullName ?? ""}`}
        description={org.data ? `Organization: ${org.data.name}` : undefined}
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {hasPermission("users:read") && (
          <Stat label="Users" value={users.data?.meta.totalItems ?? "—"} />
        )}
        {hasPermission("users:read") && <Stat label="Roles" value={roles.data?.length ?? "—"} />}
        <Stat label="Departments" value={departments.data?.length ?? "—"} />
      </div>
      <Card className="mt-6">
        <h2 className="mb-3 text-sm font-semibold">Your access</h2>
        <div className="flex flex-wrap gap-2">
          {[...permissions].sort().map((p) => (
            <Badge key={p} tone="accent">
              {p}
            </Badge>
          ))}
          {permissions.size === 0 && (
            <p className="text-sm text-muted">No permissions assigned yet.</p>
          )}
        </div>
      </Card>
      <Card className="mt-6">
        <h2 className="mb-2 text-sm font-semibold">Platform status — Phase 0</h2>
        <p className="text-sm text-muted">
          Identity &amp; access foundation is live: authentication with silent session refresh,
          role-based permissions, organization &amp; department management, and a full audit
          trail. Field operations, weather, and intelligence modules arrive in the next phases.
        </p>
      </Card>
    </div>
  );
}
