import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import type { DashboardKpis, Organization } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { Badge, Card, PageHeader, Spinner } from "@/components/ui";

function Kpi({
  label,
  value,
  tone,
  to,
}: {
  label: string;
  value: string | number;
  tone?: "warning" | "danger";
  to?: string;
}) {
  const body = (
    <Card className="h-full transition-colors hover:border-primary/50">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p
        className={[
          "mt-2 text-3xl font-semibold tabular-nums",
          tone === "danger" ? "text-destructive" : tone === "warning" ? "text-warning" : "",
        ].join(" ")}
      >
        {value}
      </p>
    </Card>
  );
  return to ? <Link to={to}>{body}</Link> : body;
}

function kg(n: number): string {
  if (n >= 1000) return `${(n / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })} t`;
  return `${n.toLocaleString()} kg`;
}

export function HomePage() {
  const { user } = useAuth();
  const org = useQuery({
    queryKey: ["organization"],
    queryFn: () => api<Organization>("/api/v1/organization"),
  });
  const kpis = useQuery({
    queryKey: ["dashboard", "kpis"],
    queryFn: () => api<DashboardKpis>("/api/v1/dashboard/kpis"),
  });

  return (
    <div>
      <PageHeader
        title="Executive overview"
        description={
          org.data
            ? `${org.data.name} · signed in as ${user?.fullName ?? ""}`
            : `Signed in as ${user?.fullName ?? ""}`
        }
      />

      {kpis.isLoading && <Spinner label="Loading KPIs…" />}
      {kpis.data && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <Kpi label="Active farmers" value={kpis.data.activeFarmers} to="/farmers" />
            <Kpi label="Active crop cycles" value={kpis.data.activeCropCycles} />
            <Kpi label="Harvested cycles" value={kpis.data.harvestedCycles} />
            <Kpi label="Seed varieties" value={kpis.data.seedVarieties} to="/varieties" />
            <Kpi label="Warehouses" value={kpis.data.warehouses} to="/inventory" />
            <Kpi label="Total stock" value={kg(kpis.data.totalStockKg)} to="/inventory" />
            <Kpi
              label="Lots expiring ≤90d"
              value={kpis.data.lotsExpiringSoon}
              tone={kpis.data.lotsExpiringSoon > 0 ? "warning" : undefined}
              to="/inventory"
            />
            <Kpi
              label="Open disease reports"
              value={kpis.data.openDiseaseReports}
              tone={kpis.data.openDiseaseReports > 0 ? "warning" : undefined}
              to="/disease-reports"
            />
            <Kpi
              label="Active outbreaks"
              value={kpis.data.activeOutbreaks}
              tone={kpis.data.activeOutbreaks > 0 ? "danger" : undefined}
              to="/disease-reports"
            />
            <Kpi
              label="Pending transfers"
              value={kpis.data.pendingTransfers}
              tone={kpis.data.pendingTransfers > 0 ? "warning" : undefined}
              to="/inventory"
            />
            <Kpi label="Open orders" value={kpis.data.openOrders} to="/logistics" />
            <Kpi label="Active routes" value={kpis.data.activeRoutes} to="/logistics" />
            <Kpi
              label="Projected production"
              value={kpis.data.yieldPredictionCount > 0 ? kg(kpis.data.projectedProductionKg) : "—"}
              to="/forecasts"
            />
            <Kpi
              label="High risks"
              value={kpis.data.highRiskCount}
              tone={kpis.data.highRiskCount > 0 ? "danger" : undefined}
              to="/risks"
            />
          </div>

          {kpis.data.activeOutbreaks > 0 && (
            <Card className="mt-6 border-destructive/40">
              <div className="flex items-center gap-3">
                <Badge tone="danger">Alert</Badge>
                <p className="text-sm">
                  {kpis.data.activeOutbreaks} active disease outbreak
                  {kpis.data.activeOutbreaks === 1 ? "" : "s"} detected.{" "}
                  <Link to="/map" className="text-accent hover:underline">
                    View on map →
                  </Link>
                </p>
              </div>
            </Card>
          )}
        </>
      )}

      <Card className="mt-6">
        <h2 className="mb-2 text-sm font-semibold">Platform status — Phase 2</h2>
        <p className="text-sm text-muted">
          Operational intelligence is live: weather forecasts &amp; agro-indicators (Open-Meteo),
          disease reporting with automatic outbreak detection, warehouse inventory with an
          append-only stock ledger and transfers, and these executive KPIs. Predictive models
          (yield, demand, risk) arrive in Phase 3.
        </p>
      </Card>
    </div>
  );
}
