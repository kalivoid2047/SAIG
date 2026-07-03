import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type {
  CropCycle,
  Farm,
  FarmerDetail,
  FieldPlot,
  Page,
  Region,
  Variety,
} from "@/lib/types";
import { useAuth } from "@/lib/auth";
import {
  Badge,
  Button,
  Card,
  Dialog,
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
import { WeatherWidget } from "@/features/weather/WeatherWidget";

const CYCLE_TONES: Record<CropCycle["status"], "neutral" | "accent" | "success" | "warning" | "danger"> = {
  planned: "neutral",
  planted: "accent",
  growing: "warning",
  harvested: "success",
  failed: "danger",
};

const NEXT_TRANSITIONS: Record<CropCycle["status"], CropCycle["status"][]> = {
  planned: ["planted", "failed"],
  planted: ["growing", "failed"],
  growing: ["harvested", "failed"],
  harvested: [],
  failed: [],
};

function useInvalidateFarmer(farmerId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["farmer", farmerId] });
    queryClient.invalidateQueries({ queryKey: ["crop-cycles"] });
  };
}

// --- Field row with its crop cycles -------------------------------------------

function FieldRow({ field, farmerId }: { field: FieldPlot; farmerId: string }) {
  const { hasPermission } = useAuth();
  const invalidate = useInvalidateFarmer(farmerId);
  const [cycleOpen, setCycleOpen] = useState(false);
  const [varietyId, setVarietyId] = useState("");
  const [season, setSeason] = useState("2026-long-rains");
  const [error, setError] = useState<string | null>(null);
  const [reportCycle, setReportCycle] = useState<string | null>(null);
  const [report, setReport] = useState({ diseaseId: "", severity: "3", affectedPct: "10" });

  const cycles = useQuery({
    queryKey: ["crop-cycles", field.id],
    queryFn: () =>
      api<Page<CropCycle>>("/api/v1/crop-cycles", {
        params: { fieldId: field.id, pageSize: 20 },
      }),
  });
  const varieties = useQuery({
    queryKey: ["varieties"],
    queryFn: () => api<Variety[]>("/api/v1/varieties"),
    enabled: cycleOpen,
  });
  const diseases = useQuery({
    queryKey: ["diseases"],
    queryFn: () => api<{ id: string; name: string; crop: string }[]>("/api/v1/diseases"),
    enabled: reportCycle !== null,
  });

  const fileReport = useMutation({
    mutationFn: () =>
      api("/api/v1/disease-reports", {
        method: "POST",
        body: {
          cropCycleId: reportCycle,
          diseaseId: report.diseaseId || null,
          severity: Number(report.severity),
          affectedPct: Number(report.affectedPct),
        },
      }),
    onSuccess: () => {
      setReportCycle(null);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not file report."),
  });

  const startCycle = useMutation({
    mutationFn: () =>
      api(`/api/v1/fields/${field.id}/crop-cycles`, {
        method: "POST",
        body: { varietyId, season },
      }),
    onSuccess: () => {
      setCycleOpen(false);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not start cycle."),
  });

  const transition = useMutation({
    mutationFn: ({ cycle, to }: { cycle: CropCycle; to: CropCycle["status"] }) => {
      let actualYieldKg: number | undefined;
      if (to === "harvested") {
        const input = prompt("Actual yield for this field (kg):");
        if (input === null) throw new ApiError(0, "cancelled");
        actualYieldKg = Number(input);
      }
      return api(`/api/v1/crop-cycles/${cycle.id}/transitions`, {
        method: "POST",
        body: { to, ...(actualYieldKg !== undefined ? { actualYieldKg } : {}) },
      });
    },
    onSuccess: invalidate,
    onError: (err) => {
      if (err instanceof ApiError && err.status !== 0) alert(err.message);
    },
  });

  return (
    <div className="rounded-md border border-border/60 bg-background/50 p-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">
          {field.name} <span className="tabular-nums text-muted">· {field.areaHa} ha</span>
          {field.boundary != null && <Badge tone="accent">mapped</Badge>}
        </p>
        {hasPermission("crops:manage") && (
          <Button variant="ghost" onClick={() => setCycleOpen(true)}>
            + Cycle
          </Button>
        )}
      </div>
      {cycles.data && cycles.data.data.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {cycles.data.data.map((cycle) => (
            <li key={cycle.id} className="flex flex-wrap items-center gap-2 text-sm">
              <Badge tone={CYCLE_TONES[cycle.status]}>{cycle.status}</Badge>
              <span className="text-muted">{cycle.season}</span>
              {cycle.actualYieldKg != null && (
                <span className="tabular-nums">{cycle.actualYieldKg} kg</span>
              )}
              {hasPermission("crops:manage") &&
                NEXT_TRANSITIONS[cycle.status].map((to) => (
                  <Button
                    key={to}
                    variant="ghost"
                    className="px-2 py-0.5 text-xs"
                    onClick={() => transition.mutate({ cycle, to })}
                  >
                    → {to}
                  </Button>
                ))}
              {hasPermission("crops:report") &&
                ["planted", "growing"].includes(cycle.status) && (
                  <Button
                    variant="ghost"
                    className="px-2 py-0.5 text-xs text-warning"
                    onClick={() => {
                      setReport({ diseaseId: "", severity: "3", affectedPct: "10" });
                      setError(null);
                      setReportCycle(cycle.id);
                    }}
                  >
                    ⚠ Report disease
                  </Button>
                )}
            </li>
          ))}
        </ul>
      )}

      <Dialog
        open={reportCycle !== null}
        onClose={() => setReportCycle(null)}
        title="Report crop disease"
      >
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setError(null);
            fileReport.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor={`rd-${field.id}`}>Disease (optional — leave blank if unidentified)</Label>
            <Select
              id={`rd-${field.id}`}
              value={report.diseaseId}
              onChange={(e) => setReport({ ...report, diseaseId: e.target.value })}
            >
              <option value="">— Unidentified —</option>
              {(diseases.data ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.crop})
                </option>
              ))}
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor={`rs-${field.id}`}>Severity</Label>
              <Select
                id={`rs-${field.id}`}
                value={report.severity}
                onChange={(e) => setReport({ ...report, severity: e.target.value })}
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n} / 5
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor={`ra-${field.id}`}>Affected %</Label>
              <Input
                id={`ra-${field.id}`}
                type="number"
                min="0"
                max="100"
                required
                value={report.affectedPct}
                onChange={(e) => setReport({ ...report, affectedPct: e.target.value })}
              />
            </div>
          </div>
          <p className="text-xs text-muted">
            The report is geotagged from this farm and scanned for outbreak clusters automatically.
          </p>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setReportCycle(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={fileReport.isPending}>
              File report
            </Button>
          </div>
        </form>
      </Dialog>

      <Dialog open={cycleOpen} onClose={() => setCycleOpen(false)} title={`New cycle — ${field.name}`}>
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setError(null);
            startCycle.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor={`cv-${field.id}`}>Seed variety</Label>
            <Select
              id={`cv-${field.id}`}
              required
              value={varietyId}
              onChange={(e) => setVarietyId(e.target.value)}
            >
              <option value="">— Select —</option>
              {(varieties.data ?? []).map((v) => (
                <option key={v.id} value={v.id}>
                  {v.crop} · {v.name} ({v.code})
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor={`cs-${field.id}`}>Season</Label>
            <Input
              id={`cs-${field.id}`}
              required
              value={season}
              onChange={(e) => setSeason(e.target.value)}
            />
          </div>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setCycleOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={startCycle.isPending}>
              Start cycle
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}

// --- Farm card -------------------------------------------------------------------

function FarmCard({ farm, farmerId }: { farm: Farm; farmerId: string }) {
  const { hasPermission } = useAuth();
  const invalidate = useInvalidateFarmer(farmerId);
  const [fieldOpen, setFieldOpen] = useState(false);
  const [name, setName] = useState("");
  const [areaHa, setAreaHa] = useState("");
  const [error, setError] = useState<string | null>(null);

  const addField = useMutation({
    mutationFn: () =>
      api(`/api/v1/farms/${farm.id}/fields`, {
        method: "POST",
        body: { name, areaHa: Number(areaHa) },
      }),
    onSuccess: () => {
      setFieldOpen(false);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not add field."),
  });

  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold">{farm.name}</h3>
          <p className="mt-0.5 text-xs tabular-nums text-muted">
            {farm.latitude.toFixed(4)}, {farm.longitude.toFixed(4)}
            {farm.totalAreaHa != null && ` · ${farm.totalAreaHa} ha total`}
          </p>
        </div>
        {hasPermission("farms:manage") && (
          <Button
            variant="secondary"
            onClick={() => {
              setName("");
              setAreaHa("");
              setError(null);
              setFieldOpen(true);
            }}
          >
            + Field
          </Button>
        )}
      </div>
      <div className="mt-3">
        <WeatherWidget farmId={farm.id} />
      </div>
      <div className="mt-3 space-y-2">
        {farm.fields.length === 0 && (
          <p className="text-sm text-muted">No fields recorded yet.</p>
        )}
        {farm.fields.map((field) => (
          <FieldRow key={field.id} field={field} farmerId={farmerId} />
        ))}
      </div>

      <Dialog open={fieldOpen} onClose={() => setFieldOpen(false)} title={`New field — ${farm.name}`}>
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            addField.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="fl-name">Field name</Label>
            <Input id="fl-name" required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="fl-area">Area (hectares)</Label>
            <Input
              id="fl-area"
              type="number"
              step="0.01"
              min="0.01"
              required
              value={areaHa}
              onChange={(e) => setAreaHa(e.target.value)}
            />
            <p className="mt-1 text-xs text-muted">
              Boundary drawing on the map arrives with GIS v2; areas can be entered manually.
            </p>
          </div>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setFieldOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={addField.isPending}>
              Add field
            </Button>
          </div>
        </form>
      </Dialog>
    </Card>
  );
}

// --- Page ---------------------------------------------------------------------------

export function FarmerDetailPage() {
  const { farmerId = "" } = useParams();
  const { hasPermission } = useAuth();
  const invalidate = useInvalidateFarmer(farmerId);
  const [farmOpen, setFarmOpen] = useState(false);
  const [farmForm, setFarmForm] = useState({ name: "", latitude: "", longitude: "" });
  const [error, setError] = useState<string | null>(null);

  const farmer = useQuery({
    queryKey: ["farmer", farmerId],
    queryFn: () => api<FarmerDetail>(`/api/v1/farmers/${farmerId}`),
  });
  const regions = useQuery({
    queryKey: ["regions"],
    queryFn: () => api<Region[]>("/api/v1/regions"),
  });

  const addFarm = useMutation({
    mutationFn: () =>
      api("/api/v1/farms", {
        method: "POST",
        body: {
          farmerId,
          name: farmForm.name,
          latitude: Number(farmForm.latitude),
          longitude: Number(farmForm.longitude),
        },
      }),
    onSuccess: () => {
      setFarmOpen(false);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not add farm."),
  });

  if (farmer.isLoading) return <Spinner />;
  if (!farmer.data) return <p className="text-sm text-muted">Farmer not found.</p>;
  const f = farmer.data;
  const regionName = regions.data?.find((r) => r.id === f.regionId)?.name ?? "—";

  return (
    <div>
      <PageHeader
        title={f.fullName}
        description={`Region: ${regionName}${f.cooperative ? ` · ${f.cooperative}` : ""}`}
        actions={
          hasPermission("farms:manage") ? (
            <Button
              onClick={() => {
                setFarmForm({ name: "", latitude: "", longitude: "" });
                setError(null);
                setFarmOpen(true);
              }}
            >
              + Add farm
            </Button>
          ) : undefined
        }
      />
      <p className="-mt-4 mb-6">
        <Link to="/farmers" className="text-xs text-accent hover:underline">
          ← All farmers
        </Link>
      </p>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            Profile
            {f.piiMasked ? (
              <Badge tone="warning">PII masked</Badge>
            ) : (
              <Badge tone="accent">PII visible — access logged</Badge>
            )}
          </h2>
          <dl className="space-y-2 text-sm">
            {[
              ["Phone", f.phone],
              ["National ID", f.nationalId],
              ["Email", f.email],
              ["Gender", f.gender],
              ["Birth year", f.birthYear?.toString()],
              [
                "Consent recorded",
                f.consentGivenAt ? new Date(f.consentGivenAt).toLocaleDateString() : null,
              ],
            ].map(([label, value]) => (
              <div key={label as string} className="flex justify-between gap-4">
                <dt className="text-muted">{label}</dt>
                <dd className="tabular-nums">{value ?? "—"}</dd>
              </div>
            ))}
          </dl>

          <h2 className="mb-2 mt-6 text-sm font-semibold">Production history</h2>
          {f.productionRecords.length === 0 ? (
            <p className="text-sm text-muted">No records yet.</p>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Season</Th>
                  <Th>Area</Th>
                  <Th>Yield</Th>
                </tr>
              </thead>
              <tbody>
                {f.productionRecords.map((r) => (
                  <tr key={r.id}>
                    <Td>{r.season}</Td>
                    <Td className="tabular-nums">{r.areaHa} ha</Td>
                    <Td className="tabular-nums">{r.yieldKg} kg</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>

        <div className="space-y-4 lg:col-span-2">
          {f.farms.length === 0 && (
            <Card>
              <p className="text-sm text-muted">No farms registered for this farmer yet.</p>
            </Card>
          )}
          {f.farms.map((farm) => (
            <FarmCard key={farm.id} farm={farm} farmerId={farmerId} />
          ))}
        </div>
      </div>

      <Dialog open={farmOpen} onClose={() => setFarmOpen(false)} title="Add farm">
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            addFarm.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="fm-name">Farm name</Label>
            <Input
              id="fm-name"
              required
              value={farmForm.name}
              onChange={(e) => setFarmForm({ ...farmForm, name: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="fm-lat">Latitude</Label>
              <Input
                id="fm-lat"
                type="number"
                step="any"
                min={-90}
                max={90}
                required
                value={farmForm.latitude}
                onChange={(e) => setFarmForm({ ...farmForm, latitude: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="fm-lng">Longitude</Label>
              <Input
                id="fm-lng"
                type="number"
                step="any"
                min={-180}
                max={180}
                required
                value={farmForm.longitude}
                onChange={(e) => setFarmForm({ ...farmForm, longitude: e.target.value })}
              />
            </div>
          </div>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setFarmOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={addFarm.isPending}>
              Add farm
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
