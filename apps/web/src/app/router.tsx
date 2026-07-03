import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Spinner } from "@/components/ui";
import { AppShell } from "./AppShell";
import { LoginPage } from "@/features/auth/LoginPage";
import { HomePage } from "@/features/home/HomePage";
import { UsersPage } from "@/features/admin/UsersPage";
import { RolesPage } from "@/features/admin/RolesPage";
import { DepartmentsPage } from "@/features/admin/DepartmentsPage";
import { AuditPage } from "@/features/admin/AuditPage";
import { FarmersPage } from "@/features/fieldops/FarmersPage";
import { FarmerDetailPage } from "@/features/fieldops/FarmerDetailPage";
import { MapPage } from "@/features/fieldops/MapPage";
import { RegionsPage } from "@/features/fieldops/RegionsPage";
import { VarietiesPage } from "@/features/catalog/VarietiesPage";

function Protected() {
  const { status } = useAuth();
  if (status === "loading") {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner label="Restoring session…" />
      </div>
    );
  }
  if (status === "anonymous") return <Navigate to="/login" replace />;
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

/** Route-level permission guard: renders nothing the user may not see. */
function RequirePermission({ permission }: { permission: string }) {
  const { hasPermission } = useAuth();
  if (!hasPermission(permission)) return <Navigate to="/" replace />;
  return <Outlet />;
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<Protected />}>
          <Route path="/" element={<HomePage />} />
          <Route element={<RequirePermission permission="farmers:read" />}>
            <Route path="/farmers" element={<FarmersPage />} />
            <Route path="/farmers/:farmerId" element={<FarmerDetailPage />} />
          </Route>
          <Route element={<RequirePermission permission="farms:read" />}>
            <Route path="/map" element={<MapPage />} />
          </Route>
          <Route element={<RequirePermission permission="varieties:read" />}>
            <Route path="/varieties" element={<VarietiesPage />} />
          </Route>
          <Route element={<RequirePermission permission="regions:manage" />}>
            <Route path="/admin/regions" element={<RegionsPage />} />
          </Route>
          <Route element={<RequirePermission permission="users:read" />}>
            <Route path="/admin/users" element={<UsersPage />} />
          </Route>
          <Route element={<RequirePermission permission="roles:manage" />}>
            <Route path="/admin/roles" element={<RolesPage />} />
          </Route>
          <Route element={<RequirePermission permission="org:manage" />}>
            <Route path="/admin/departments" element={<DepartmentsPage />} />
          </Route>
          <Route element={<RequirePermission permission="audit:read" />}>
            <Route path="/admin/audit" element={<AuditPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
