import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type {
  StockBalance,
  StockLot,
  StockTransfer,
  Variety,
  Warehouse,
} from "@/lib/types";
import { useAuth } from "@/lib/auth";
import {
  Badge,
  Button,
  Card,
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

type Tab = "stock" | "warehouses" | "transfers";

export function InventoryPage() {
  const { hasPermission } = useAuth();
  const [tab, setTab] = useState<Tab>("stock");

  const tabs: { id: Tab; label: string }[] = [
    { id: "stock", label: "Stock balances" },
    { id: "warehouses", label: "Warehouses & lots" },
    { id: "transfers", label: "Transfers" },
  ];

  return (
    <div>
      <PageHeader
        title="Inventory"
        description="Warehouses, seed lots, and an append-only stock ledger."
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

      {tab === "stock" && <StockTab canMove={hasPermission("inventory:move")} />}
      {tab === "warehouses" && <WarehousesTab canManage={hasPermission("inventory:manage")} />}
      {tab === "transfers" && <TransfersTab canTransfer={hasPermission("inventory:transfer")} />}
    </div>
  );
}

function fmtKg(n: number): string {
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 1 })} kg`;
}

// --- Stock balances + movement ------------------------------------------------

function StockTab({ canMove }: { canMove: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ warehouseId: "", lotId: "", quantityKg: "" });
  const [error, setError] = useState<string | null>(null);

  const balances = useQuery({
    queryKey: ["stock", "balances"],
    queryFn: () => api<StockBalance[]>("/api/v1/stock/balances"),
  });
  const warehouses = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api<Warehouse[]>("/api/v1/warehouses"),
  });
  const lots = useQuery({
    queryKey: ["lots"],
    queryFn: () => api<StockLot[]>("/api/v1/stock/lots"),
  });

  const whName = (id: string) => warehouses.data?.find((w) => w.id === id)?.name ?? id.slice(0, 8);

  const receive = useMutation({
    mutationFn: () =>
      api("/api/v1/stock/movements", {
        method: "POST",
        body: {
          warehouseId: form.warehouseId,
          lotId: form.lotId,
          movementType: "receipt",
          quantityKg: Number(form.quantityKg),
        },
      }),
    onSuccess: () => {
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["stock"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  return (
    <div>
      {canMove && (
        <div className="mb-4">
          <Button
            onClick={() => {
              setForm({ warehouseId: "", lotId: "", quantityKg: "" });
              setError(null);
              setOpen(true);
            }}
          >
            + Record receipt
          </Button>
        </div>
      )}
      {balances.isLoading && <Spinner />}
      {balances.data && balances.data.length === 0 && (
        <EmptyState title="No stock on hand" hint="Record a receipt to add stock." />
      )}
      {balances.data && balances.data.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Warehouse</Th>
              <Th>Lot</Th>
              <Th>Balance</Th>
              <Th>Expires</Th>
            </tr>
          </thead>
          <tbody>
            {balances.data.map((b) => (
              <tr key={`${b.warehouseId}-${b.lotId}`} className="hover:bg-elevated/40">
                <Td className="font-medium">{whName(b.warehouseId)}</Td>
                <Td className="font-mono text-xs">{b.lotNumber}</Td>
                <Td className="tabular-nums">{fmtKg(b.balanceKg)}</Td>
                <Td className="tabular-nums">
                  {b.expiringSoon ? (
                    <Badge tone="warning">{b.expiresAt}</Badge>
                  ) : (
                    <span className="text-muted">{b.expiresAt}</span>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="Record stock receipt">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setError(null);
            receive.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="m-wh">Warehouse</Label>
            <Select
              id="m-wh"
              required
              value={form.warehouseId}
              onChange={(e) => setForm({ ...form, warehouseId: e.target.value })}
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
            <Label htmlFor="m-lot">Lot</Label>
            <Select
              id="m-lot"
              required
              value={form.lotId}
              onChange={(e) => setForm({ ...form, lotId: e.target.value })}
            >
              <option value="">— Select —</option>
              {(lots.data ?? []).map((l) => (
                <option key={l.id} value={l.id}>
                  {l.lotNumber} (exp {l.expiresAt})
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="m-qty">Quantity (kg)</Label>
            <Input
              id="m-qty"
              type="number"
              step="0.1"
              min="0.1"
              required
              value={form.quantityKg}
              onChange={(e) => setForm({ ...form, quantityKg: e.target.value })}
            />
          </div>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={receive.isPending}>
              Record
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}

// --- Warehouses + lots --------------------------------------------------------

function WarehousesTab({ canManage }: { canManage: boolean }) {
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<"warehouse" | "lot" | null>(null);
  const [wForm, setWForm] = useState({ name: "", code: "", latitude: "", longitude: "" });
  const [lForm, setLForm] = useState({
    varietyId: "",
    lotNumber: "",
    producedAt: "",
    expiresAt: "",
  });
  const [error, setError] = useState<string | null>(null);

  const warehouses = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api<Warehouse[]>("/api/v1/warehouses"),
  });
  const lots = useQuery({
    queryKey: ["lots"],
    queryFn: () => api<StockLot[]>("/api/v1/stock/lots"),
  });
  const varieties = useQuery({
    queryKey: ["varieties"],
    queryFn: () => api<Variety[]>("/api/v1/varieties"),
  });

  const createWarehouse = useMutation({
    mutationFn: () =>
      api("/api/v1/warehouses", {
        method: "POST",
        body: {
          name: wForm.name,
          code: wForm.code,
          latitude: Number(wForm.latitude),
          longitude: Number(wForm.longitude),
        },
      }),
    onSuccess: () => {
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["warehouses"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  const createLot = useMutation({
    mutationFn: () =>
      api("/api/v1/stock/lots", {
        method: "POST",
        body: {
          varietyId: lForm.varietyId,
          lotNumber: lForm.lotNumber,
          producedAt: lForm.producedAt,
          expiresAt: lForm.expiresAt,
        },
      }),
    onSuccess: () => {
      setDialog(null);
      queryClient.invalidateQueries({ queryKey: ["lots"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Warehouses</h3>
          {canManage && (
            <Button
              variant="secondary"
              onClick={() => {
                setWForm({ name: "", code: "", latitude: "", longitude: "" });
                setError(null);
                setDialog("warehouse");
              }}
            >
              + New
            </Button>
          )}
        </div>
        {warehouses.isLoading && <Spinner />}
        <ul className="space-y-2">
          {(warehouses.data ?? []).map((w) => (
            <li key={w.id} className="flex justify-between border-b border-border/60 pb-2 text-sm">
              <span className="font-medium">{w.name}</span>
              <span className="font-mono text-xs text-muted">{w.code}</span>
            </li>
          ))}
          {warehouses.data?.length === 0 && <p className="text-sm text-muted">None yet.</p>}
        </ul>
      </Card>

      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Seed lots</h3>
          {canManage && (
            <Button
              variant="secondary"
              onClick={() => {
                setLForm({ varietyId: "", lotNumber: "", producedAt: "", expiresAt: "" });
                setError(null);
                setDialog("lot");
              }}
            >
              + New
            </Button>
          )}
        </div>
        {lots.isLoading && <Spinner />}
        <ul className="space-y-2">
          {(lots.data ?? []).map((l) => (
            <li key={l.id} className="flex justify-between border-b border-border/60 pb-2 text-sm">
              <span className="font-mono text-xs">{l.lotNumber}</span>
              <span className="text-muted">exp {l.expiresAt}</span>
            </li>
          ))}
          {lots.data?.length === 0 && <p className="text-sm text-muted">None yet.</p>}
        </ul>
      </Card>

      <Dialog
        open={dialog === "warehouse"}
        onClose={() => setDialog(null)}
        title="New warehouse"
      >
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setError(null);
            createWarehouse.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="w-name">Name</Label>
            <Input
              id="w-name"
              required
              value={wForm.name}
              onChange={(e) => setWForm({ ...wForm, name: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="w-code">Code</Label>
            <Input
              id="w-code"
              required
              value={wForm.code}
              onChange={(e) => setWForm({ ...wForm, code: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="w-lat">Latitude</Label>
              <Input
                id="w-lat"
                type="number"
                step="any"
                required
                value={wForm.latitude}
                onChange={(e) => setWForm({ ...wForm, latitude: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="w-lng">Longitude</Label>
              <Input
                id="w-lng"
                type="number"
                step="any"
                required
                value={wForm.longitude}
                onChange={(e) => setWForm({ ...wForm, longitude: e.target.value })}
              />
            </div>
          </div>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDialog(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createWarehouse.isPending}>
              Create
            </Button>
          </div>
        </form>
      </Dialog>

      <Dialog open={dialog === "lot"} onClose={() => setDialog(null)} title="New seed lot">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setError(null);
            createLot.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="l-variety">Variety</Label>
            <Select
              id="l-variety"
              required
              value={lForm.varietyId}
              onChange={(e) => setLForm({ ...lForm, varietyId: e.target.value })}
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
            <Label htmlFor="l-number">Lot number</Label>
            <Input
              id="l-number"
              required
              value={lForm.lotNumber}
              onChange={(e) => setLForm({ ...lForm, lotNumber: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="l-prod">Produced</Label>
              <Input
                id="l-prod"
                type="date"
                required
                value={lForm.producedAt}
                onChange={(e) => setLForm({ ...lForm, producedAt: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="l-exp">Expires</Label>
              <Input
                id="l-exp"
                type="date"
                required
                value={lForm.expiresAt}
                onChange={(e) => setLForm({ ...lForm, expiresAt: e.target.value })}
              />
            </div>
          </div>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDialog(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createLot.isPending}>
              Create
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}

// --- Transfers ----------------------------------------------------------------

function TransfersTab({ canTransfer }: { canTransfer: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    fromWarehouseId: "",
    toWarehouseId: "",
    lotId: "",
    quantityKg: "",
  });
  const [error, setError] = useState<string | null>(null);

  const transfers = useQuery({
    queryKey: ["transfers"],
    queryFn: () => api<StockTransfer[]>("/api/v1/stock/transfers"),
  });
  const warehouses = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api<Warehouse[]>("/api/v1/warehouses"),
  });
  const lots = useQuery({
    queryKey: ["lots"],
    queryFn: () => api<StockLot[]>("/api/v1/stock/lots"),
  });

  const whName = (id: string) => warehouses.data?.find((w) => w.id === id)?.code ?? id.slice(0, 6);
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["transfers"] });
    queryClient.invalidateQueries({ queryKey: ["stock"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const create = useMutation({
    mutationFn: () =>
      api("/api/v1/stock/transfers", {
        method: "POST",
        body: {
          fromWarehouseId: form.fromWarehouseId,
          toWarehouseId: form.toWarehouseId,
          lotId: form.lotId,
          quantityKg: Number(form.quantityKg),
        },
      }),
    onSuccess: () => {
      setOpen(false);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  const act = useMutation({
    mutationFn: ({ id, action, receivedKg }: { id: string; action: string; receivedKg?: number }) =>
      api(`/api/v1/stock/transfers/${id}/${action}`, {
        method: "POST",
        body: receivedKg !== undefined ? { receivedKg } : undefined,
      }),
    onSuccess: invalidate,
    onError: (err) => alert(err instanceof ApiError ? err.message : "Failed."),
  });

  const tones = {
    pending: "neutral",
    dispatched: "accent",
    received: "success",
    cancelled: "danger",
  } as const;

  return (
    <div>
      {canTransfer && (
        <div className="mb-4">
          <Button
            onClick={() => {
              setForm({ fromWarehouseId: "", toWarehouseId: "", lotId: "", quantityKg: "" });
              setError(null);
              setOpen(true);
            }}
          >
            + New transfer
          </Button>
        </div>
      )}
      {transfers.isLoading && <Spinner />}
      {transfers.data && transfers.data.length === 0 && <EmptyState title="No transfers yet" />}
      {transfers.data && transfers.data.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Route</Th>
              <Th>Qty</Th>
              <Th>Status</Th>
              <Th>Received</Th>
              {canTransfer && <Th />}
            </tr>
          </thead>
          <tbody>
            {transfers.data.map((t) => (
              <tr key={t.id} className="hover:bg-elevated/40">
                <Td className="font-mono text-xs">
                  {whName(t.fromWarehouseId)} → {whName(t.toWarehouseId)}
                </Td>
                <Td className="tabular-nums">{fmtKg(t.quantityKg)}</Td>
                <Td>
                  <Badge tone={tones[t.status]}>{t.status}</Badge>
                  {t.varianceNote && <Badge tone="warning">variance</Badge>}
                </Td>
                <Td className="tabular-nums text-muted">
                  {t.receivedKg != null ? fmtKg(t.receivedKg) : "—"}
                </Td>
                {canTransfer && (
                  <Td>
                    <div className="flex justify-end gap-1">
                      {t.status === "pending" && (
                        <>
                          <Button
                            variant="ghost"
                            onClick={() => act.mutate({ id: t.id, action: "dispatch" })}
                          >
                            Dispatch
                          </Button>
                          <Button
                            variant="ghost"
                            className="text-destructive"
                            onClick={() => act.mutate({ id: t.id, action: "cancel" })}
                          >
                            Cancel
                          </Button>
                        </>
                      )}
                      {t.status === "dispatched" && (
                        <Button
                          variant="ghost"
                          onClick={() => {
                            const input = prompt(
                              `Received quantity (kg), dispatched ${t.quantityKg}:`,
                              String(t.quantityKg),
                            );
                            if (input !== null) {
                              act.mutate({ id: t.id, action: "receive", receivedKg: Number(input) });
                            }
                          }}
                        >
                          Receive
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

      <Dialog open={open} onClose={() => setOpen(false)} title="New stock transfer">
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
              <Label htmlFor="t-from">From</Label>
              <Select
                id="t-from"
                required
                value={form.fromWarehouseId}
                onChange={(e) => setForm({ ...form, fromWarehouseId: e.target.value })}
              >
                <option value="">—</option>
                {(warehouses.data ?? []).map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="t-to">To</Label>
              <Select
                id="t-to"
                required
                value={form.toWarehouseId}
                onChange={(e) => setForm({ ...form, toWarehouseId: e.target.value })}
              >
                <option value="">—</option>
                {(warehouses.data ?? []).map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <div>
            <Label htmlFor="t-lot">Lot</Label>
            <Select
              id="t-lot"
              required
              value={form.lotId}
              onChange={(e) => setForm({ ...form, lotId: e.target.value })}
            >
              <option value="">— Select —</option>
              {(lots.data ?? []).map((l) => (
                <option key={l.id} value={l.id}>
                  {l.lotNumber}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="t-qty">Quantity (kg)</Label>
            <Input
              id="t-qty"
              type="number"
              step="0.1"
              min="0.1"
              required
              value={form.quantityKg}
              onChange={(e) => setForm({ ...form, quantityKg: e.target.value })}
            />
          </div>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              Create transfer
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
