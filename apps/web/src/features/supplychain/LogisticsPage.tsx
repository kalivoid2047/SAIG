import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type {
  Delivery,
  Order,
  Page,
  RoutePlan,
  Variety,
  Vehicle,
  Warehouse,
} from "@/lib/types";
import { useAuth } from "@/lib/auth";
import {
  Badge,
  Button,
  Dialog,
  EmptyState,
  ErrorNote,
  Input,
  Label,
  PageHeader,
  Select,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";

type Tab = "orders" | "routes" | "vehicles" | "deliveries";

export function LogisticsPage() {
  const { hasPermission } = useAuth();
  const [tab, setTab] = useState<Tab>("orders");
  const tabs: { id: Tab; label: string }[] = [
    { id: "orders", label: "Orders" },
    { id: "routes", label: "Routes" },
    { id: "deliveries", label: "Deliveries" },
    { id: "vehicles", label: "Vehicles" },
  ];

  return (
    <div>
      <PageHeader
        title="Supply chain"
        description="Customer orders, delivery route planning, vehicles and live delivery tracking."
      />
      <div className="mb-4 flex gap-1 border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={[
              "border-b-2 px-4 py-2 text-sm font-medium transition-colors",
              tab === t.id
                ? "border-primary text-primary"
                : "border-transparent text-muted hover:text-foreground",
            ].join(" ")}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "orders" && <OrdersTab canManage={hasPermission("logistics:manage")} />}
      {tab === "routes" && <RoutesTab canPlan={hasPermission("logistics:plan")} />}
      {tab === "deliveries" && <DeliveriesTab canTrack={hasPermission("logistics:track")} />}
      {tab === "vehicles" && <VehiclesTab canManage={hasPermission("logistics:manage")} />}
    </div>
  );
}

const ORDER_TONES = {
  pending: "warning",
  confirmed: "accent",
  fulfilled: "success",
  cancelled: "neutral",
} as const;

function fmtKg(n: number): string {
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 1 })} kg`;
}

// --- Orders ------------------------------------------------------------------

function OrdersTab({ canManage }: { canManage: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    customerName: "",
    destinationLat: "",
    destinationLng: "",
    varietyId: "",
    quantityKg: "",
  });
  const [error, setError] = useState<string | null>(null);

  const orders = useQuery({
    queryKey: ["orders"],
    queryFn: () => api<Page<Order>>("/api/v1/orders", { params: { pageSize: 50 } }),
  });
  const varieties = useQuery({
    queryKey: ["varieties"],
    queryFn: () => api<Variety[]>("/api/v1/varieties"),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["orders"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const create = useMutation({
    mutationFn: () =>
      api("/api/v1/orders", {
        method: "POST",
        body: {
          customerName: form.customerName,
          destinationLat: Number(form.destinationLat),
          destinationLng: Number(form.destinationLng),
          items: [{ varietyId: form.varietyId, quantityKg: Number(form.quantityKg) }],
        },
      }),
    onSuccess: () => {
      setOpen(false);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api(`/api/v1/orders/${id}/status`, { method: "POST", body: { status } }),
    onSuccess: invalidate,
    onError: (err) => alert(err instanceof ApiError ? err.message : "Failed."),
  });

  return (
    <div>
      {canManage && (
        <div className="mb-4">
          <Button
            onClick={() => {
              setForm({ customerName: "", destinationLat: "", destinationLng: "", varietyId: "", quantityKg: "" });
              setError(null);
              setOpen(true);
            }}
          >
            + New order
          </Button>
        </div>
      )}
      {orders.isLoading && <Spinner />}
      {orders.data && orders.data.data.length === 0 && <EmptyState title="No orders yet" />}
      {orders.data && orders.data.data.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Customer</Th>
              <Th>Items</Th>
              <Th>Status</Th>
              <Th>Destination</Th>
              {canManage && <Th />}
            </tr>
          </thead>
          <tbody>
            {orders.data.data.map((o) => (
              <tr key={o.id} className="hover:bg-elevated/40">
                <Td className="font-medium">{o.customerName}</Td>
                <Td className="tabular-nums text-muted">
                  {fmtKg(o.items.reduce((s, i) => s + i.quantityKg, 0))}
                </Td>
                <Td>
                  <Badge tone={ORDER_TONES[o.status]}>{o.status}</Badge>
                </Td>
                <Td className="font-mono text-xs text-muted">
                  {o.destinationLat.toFixed(3)}, {o.destinationLng.toFixed(3)}
                </Td>
                {canManage && (
                  <Td>
                    <div className="flex justify-end gap-1">
                      {o.status === "pending" && (
                        <>
                          <Button
                            variant="ghost"
                            onClick={() => setStatus.mutate({ id: o.id, status: "confirmed" })}
                          >
                            Confirm
                          </Button>
                          <Button
                            variant="ghost"
                            className="text-destructive"
                            onClick={() => setStatus.mutate({ id: o.id, status: "cancelled" })}
                          >
                            Cancel
                          </Button>
                        </>
                      )}
                    </div>
                  </Td>
                )}
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="New order">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setError(null);
            create.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="o-cust">Customer name</Label>
            <Input
              id="o-cust"
              required
              value={form.customerName}
              onChange={(e) => setForm({ ...form, customerName: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="o-lat">Destination latitude</Label>
              <Input
                id="o-lat"
                type="number"
                step="any"
                required
                value={form.destinationLat}
                onChange={(e) => setForm({ ...form, destinationLat: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="o-lng">Destination longitude</Label>
              <Input
                id="o-lng"
                type="number"
                step="any"
                required
                value={form.destinationLng}
                onChange={(e) => setForm({ ...form, destinationLng: e.target.value })}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="o-var">Variety</Label>
              <Select
                id="o-var"
                required
                value={form.varietyId}
                onChange={(e) => setForm({ ...form, varietyId: e.target.value })}
              >
                <option value="">— Select —</option>
                {(varieties.data ?? []).map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} ({v.code})
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="o-qty">Quantity (kg)</Label>
              <Input
                id="o-qty"
                type="number"
                step="0.1"
                min="0.1"
                required
                value={form.quantityKg}
                onChange={(e) => setForm({ ...form, quantityKg: e.target.value })}
              />
            </div>
          </div>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              Create order
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}

// --- Routes ------------------------------------------------------------------

const ROUTE_TONES = {
  draft: "neutral",
  planned: "accent",
  dispatched: "warning",
  completed: "success",
  cancelled: "neutral",
} as const;

function RoutesTab({ canPlan }: { canPlan: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ originWarehouseId: "", vehicleId: "", plannedDate: "" });
  const [orderIds, setOrderIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const routes = useQuery({
    queryKey: ["routes"],
    queryFn: () => api<RoutePlan[]>("/api/v1/routes"),
  });
  const warehouses = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api<Warehouse[]>("/api/v1/warehouses"),
  });
  const vehicles = useQuery({
    queryKey: ["vehicles"],
    queryFn: () => api<Vehicle[]>("/api/v1/vehicles"),
  });
  const orders = useQuery({
    queryKey: ["orders", "confirmed"],
    queryFn: () => api<Page<Order>>("/api/v1/orders", { params: { status: "confirmed", pageSize: 50 } }),
    enabled: open,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["routes"] });
    queryClient.invalidateQueries({ queryKey: ["vehicles"] });
    queryClient.invalidateQueries({ queryKey: ["deliveries"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const create = useMutation({
    mutationFn: () =>
      api("/api/v1/routes", {
        method: "POST",
        body: {
          originWarehouseId: form.originWarehouseId,
          plannedDate: form.plannedDate,
          vehicleId: form.vehicleId || null,
          orderIds,
        },
      }),
    onSuccess: () => {
      setOpen(false);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  const dispatch = useMutation({
    mutationFn: (id: string) => api(`/api/v1/routes/${id}/dispatch`, { method: "POST" }),
    onSuccess: invalidate,
    onError: (err) => alert(err instanceof ApiError ? err.message : "Failed."),
  });

  return (
    <div>
      {canPlan && (
        <div className="mb-4">
          <Button
            onClick={() => {
              setForm({ originWarehouseId: "", vehicleId: "", plannedDate: "" });
              setOrderIds([]);
              setError(null);
              setOpen(true);
            }}
          >
            + Plan route
          </Button>
        </div>
      )}
      {routes.isLoading && <Spinner />}
      {routes.data && routes.data.length === 0 && <EmptyState title="No routes planned" />}
      {routes.data && routes.data.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Date</Th>
              <Th>Stops</Th>
              <Th>Distance</Th>
              <Th>Status</Th>
              {canPlan && <Th />}
            </tr>
          </thead>
          <tbody>
            {routes.data.map((r) => (
              <tr key={r.id} className="hover:bg-elevated/40">
                <Td className="tabular-nums">{r.plannedDate}</Td>
                <Td className="tabular-nums">{r.stops.length}</Td>
                <Td className="tabular-nums text-muted">
                  {r.totalDistanceKm != null ? `${r.totalDistanceKm} km` : "—"}
                </Td>
                <Td>
                  <Badge tone={ROUTE_TONES[r.status]}>{r.status}</Badge>
                </Td>
                {canPlan && (
                  <Td>
                    <div className="flex justify-end">
                      {r.status === "planned" && (
                        <Button variant="ghost" onClick={() => dispatch.mutate(r.id)}>
                          Dispatch
                        </Button>
                      )}
                    </div>
                  </Td>
                )}
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="Plan delivery route">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setError(null);
            create.mutate();
          }}
          className="space-y-4"
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="r-wh">Origin warehouse</Label>
              <Select
                id="r-wh"
                required
                value={form.originWarehouseId}
                onChange={(e) => setForm({ ...form, originWarehouseId: e.target.value })}
              >
                <option value="">— Select —</option>
                {(warehouses.data ?? []).map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="r-date">Planned date</Label>
              <Input
                id="r-date"
                type="date"
                required
                value={form.plannedDate}
                onChange={(e) => setForm({ ...form, plannedDate: e.target.value })}
              />
            </div>
          </div>
          <div>
            <Label htmlFor="r-veh">Vehicle (optional)</Label>
            <Select
              id="r-veh"
              value={form.vehicleId}
              onChange={(e) => setForm({ ...form, vehicleId: e.target.value })}
            >
              <option value="">— Unassigned —</option>
              {(vehicles.data ?? [])
                .filter((v) => v.status === "available")
                .map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.registration} ({fmtKg(v.capacityKg)})
                  </option>
                ))}
            </Select>
          </div>
          <fieldset>
            <legend className="mb-1 block text-xs font-medium text-muted">
              Confirmed orders to include
            </legend>
            <div className="max-h-40 space-y-1.5 overflow-y-auto">
              {(orders.data?.data ?? []).map((o) => (
                <label key={o.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={orderIds.includes(o.id)}
                    onChange={(e) =>
                      setOrderIds(
                        e.target.checked
                          ? [...orderIds, o.id]
                          : orderIds.filter((id) => id !== o.id),
                      )
                    }
                  />
                  {o.customerName} · {fmtKg(o.items.reduce((s, i) => s + i.quantityKg, 0))}
                </label>
              ))}
              {orders.data?.data.length === 0 && (
                <p className="text-xs text-muted">No confirmed orders available.</p>
              )}
            </div>
          </fieldset>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending || orderIds.length === 0}>
              Plan route
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}

// --- Deliveries --------------------------------------------------------------

const DELIVERY_TONES = {
  pending: "neutral",
  assigned: "accent",
  in_transit: "warning",
  delivered: "success",
  failed: "danger",
} as const;

function DeliveriesTab({ canTrack }: { canTrack: boolean }) {
  const queryClient = useQueryClient();
  const deliveries = useQuery({
    queryKey: ["deliveries"],
    queryFn: () => api<Delivery[]>("/api/v1/deliveries"),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["deliveries"] });
    queryClient.invalidateQueries({ queryKey: ["orders"] });
    queryClient.invalidateQueries({ queryKey: ["routes"] });
    queryClient.invalidateQueries({ queryKey: ["vehicles"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const event = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api(`/api/v1/deliveries/${id}/events`, {
        method: "POST",
        body: { eventType: "status_change", status },
      }),
    onSuccess: invalidate,
    onError: (err) => alert(err instanceof ApiError ? err.message : "Failed."),
  });

  return (
    <div>
      {deliveries.isLoading && <Spinner />}
      {deliveries.data && deliveries.data.length === 0 && (
        <EmptyState title="No deliveries" hint="Dispatch a route to create deliveries." />
      )}
      {deliveries.data && deliveries.data.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Delivery</Th>
              <Th>Status</Th>
              <Th>Delivered</Th>
              {canTrack && <Th />}
            </tr>
          </thead>
          <tbody>
            {deliveries.data.map((d) => (
              <tr key={d.id} className="hover:bg-elevated/40">
                <Td className="font-mono text-xs">{d.id.slice(0, 8)}</Td>
                <Td>
                  <Badge tone={DELIVERY_TONES[d.status]}>{d.status.replace("_", " ")}</Badge>
                </Td>
                <Td className="tabular-nums text-muted">
                  {d.deliveredAt ? new Date(d.deliveredAt).toLocaleString() : "—"}
                </Td>
                {canTrack && (
                  <Td>
                    <div className="flex justify-end gap-1">
                      {d.status === "in_transit" && (
                        <>
                          <Button
                            variant="ghost"
                            onClick={() => event.mutate({ id: d.id, status: "delivered" })}
                          >
                            Mark delivered
                          </Button>
                          <Button
                            variant="ghost"
                            className="text-destructive"
                            onClick={() => event.mutate({ id: d.id, status: "failed" })}
                          >
                            Failed
                          </Button>
                        </>
                      )}
                    </div>
                  </Td>
                )}
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}

// --- Vehicles ----------------------------------------------------------------

const VEHICLE_TONES = {
  available: "success",
  on_route: "warning",
  maintenance: "accent",
  retired: "neutral",
} as const;

function VehiclesTab({ canManage }: { canManage: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ registration: "", capacityKg: "" });
  const [error, setError] = useState<string | null>(null);

  const vehicles = useQuery({
    queryKey: ["vehicles"],
    queryFn: () => api<Vehicle[]>("/api/v1/vehicles"),
  });

  const create = useMutation({
    mutationFn: () =>
      api("/api/v1/vehicles", {
        method: "POST",
        body: { registration: form.registration, capacityKg: Number(form.capacityKg) },
      }),
    onSuccess: () => {
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["vehicles"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  return (
    <div>
      {canManage && (
        <div className="mb-4">
          <Button
            onClick={() => {
              setForm({ registration: "", capacityKg: "" });
              setError(null);
              setOpen(true);
            }}
          >
            + New vehicle
          </Button>
        </div>
      )}
      {vehicles.isLoading && <Spinner />}
      {vehicles.data && vehicles.data.length === 0 && <EmptyState title="No vehicles" />}
      {vehicles.data && vehicles.data.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Registration</Th>
              <Th>Capacity</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody>
            {vehicles.data.map((v) => (
              <tr key={v.id} className="hover:bg-elevated/40">
                <Td className="font-mono">{v.registration}</Td>
                <Td className="tabular-nums text-muted">{fmtKg(v.capacityKg)}</Td>
                <Td>
                  <Badge tone={VEHICLE_TONES[v.status]}>{v.status.replace("_", " ")}</Badge>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="New vehicle">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setError(null);
            create.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="v-reg">Registration</Label>
            <Input
              id="v-reg"
              required
              value={form.registration}
              onChange={(e) => setForm({ ...form, registration: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="v-cap">Capacity (kg)</Label>
            <Input
              id="v-cap"
              type="number"
              step="1"
              min="1"
              required
              value={form.capacityKg}
              onChange={(e) => setForm({ ...form, capacityKg: e.target.value })}
            />
          </div>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              Create
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
