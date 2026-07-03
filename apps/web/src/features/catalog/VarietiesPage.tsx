import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { Region, Variety } from "@/lib/types";
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

interface VarietyForm {
  crop: string;
  name: string;
  code: string;
  maturityDays: string;
  yieldPotentialKgHa: string;
  droughtTolerance: string;
  diseaseTolerance: string;
}

const EMPTY: VarietyForm = {
  crop: "",
  name: "",
  code: "",
  maturityDays: "",
  yieldPotentialKgHa: "",
  droughtTolerance: "",
  diseaseTolerance: "",
};

function tolerance(value: number | null): string {
  return value == null ? "—" : "●".repeat(value) + "○".repeat(5 - value);
}

export function VarietiesPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("varieties:manage");
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<"create" | Variety | null>(null);
  const [suitabilityFor, setSuitabilityFor] = useState<Variety | null>(null);
  const [form, setForm] = useState<VarietyForm>(EMPTY);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);

  const varieties = useQuery({
    queryKey: ["varieties"],
    queryFn: () => api<Variety[]>("/api/v1/varieties"),
  });
  const regions = useQuery({
    queryKey: ["regions"],
    queryFn: () => api<Region[]>("/api/v1/regions"),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["varieties"] });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const numeric = (v: string) => (v === "" ? null : Number(v));
      const body = {
        crop: form.crop,
        name: form.name,
        maturityDays: numeric(form.maturityDays),
        yieldPotentialKgHa: numeric(form.yieldPotentialKgHa),
        droughtTolerance: numeric(form.droughtTolerance),
        diseaseTolerance: numeric(form.diseaseTolerance),
      };
      if (dialog === "create") {
        await api("/api/v1/varieties", { method: "POST", body: { ...body, code: form.code } });
      } else if (dialog) {
        await api(`/api/v1/varieties/${dialog.id}`, { method: "PATCH", body });
      }
    },
    onSuccess: () => {
      setDialog(null);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Request failed."),
  });

  const suitabilityMutation = useMutation({
    mutationFn: () =>
      api(`/api/v1/varieties/${suitabilityFor!.id}/suitability`, {
        method: "PUT",
        body: Object.entries(scores)
          .filter(([, score]) => score > 0)
          .map(([regionId, score]) => ({ regionId, score })),
      }),
    onSuccess: () => {
      setSuitabilityFor(null);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Request failed."),
  });

  function open(target: "create" | Variety) {
    setError(null);
    if (target === "create") {
      setForm(EMPTY);
    } else {
      setForm({
        crop: target.crop,
        name: target.name,
        code: target.code,
        maturityDays: target.maturityDays?.toString() ?? "",
        yieldPotentialKgHa: target.yieldPotentialKgHa?.toString() ?? "",
        droughtTolerance: target.droughtTolerance?.toString() ?? "",
        diseaseTolerance: target.diseaseTolerance?.toString() ?? "",
      });
    }
    setDialog(target);
  }

  function openSuitability(variety: Variety) {
    setError(null);
    setScores(
      Object.fromEntries(variety.suitability.map((s) => [s.regionId, s.score])),
    );
    setSuitabilityFor(variety);
  }

  const data = varieties.data ?? [];

  return (
    <div>
      <PageHeader
        title="Seed varieties"
        description="The product catalog: agronomic traits and regional suitability."
        actions={canManage ? <Button onClick={() => open("create")}>+ New variety</Button> : undefined}
      />

      {varieties.isLoading && <Spinner />}
      {!varieties.isLoading && data.length === 0 && (
        <EmptyState title="No varieties in the catalog" />
      )}
      {data.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Crop</Th>
              <Th>Name</Th>
              <Th>Code</Th>
              <Th>Maturity</Th>
              <Th>Potential</Th>
              <Th>Drought tol.</Th>
              <Th>Disease tol.</Th>
              <Th>Suitability</Th>
              {canManage && <Th />}
            </tr>
          </thead>
          <tbody>
            {data.map((v) => (
              <tr key={v.id} className="hover:bg-elevated/40">
                <Td className="capitalize">{v.crop}</Td>
                <Td className="font-medium">{v.name}</Td>
                <Td className="font-mono text-xs">{v.code}</Td>
                <Td className="tabular-nums text-muted">
                  {v.maturityDays ? `${v.maturityDays} d` : "—"}
                </Td>
                <Td className="tabular-nums text-muted">
                  {v.yieldPotentialKgHa ? `${v.yieldPotentialKgHa} kg/ha` : "—"}
                </Td>
                <Td className="tabular-nums">{tolerance(v.droughtTolerance)}</Td>
                <Td className="tabular-nums">{tolerance(v.diseaseTolerance)}</Td>
                <Td>
                  <Badge tone={v.suitability.length > 0 ? "accent" : "neutral"}>
                    {v.suitability.length} region{v.suitability.length === 1 ? "" : "s"}
                  </Badge>
                </Td>
                {canManage && (
                  <Td>
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" onClick={() => open(v)}>
                        Edit
                      </Button>
                      <Button variant="ghost" onClick={() => openSuitability(v)}>
                        Suitability
                      </Button>
                    </div>
                  </Td>
                )}
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      <Dialog
        open={dialog !== null}
        onClose={() => setDialog(null)}
        title={dialog === "create" ? "New variety" : "Edit variety"}
      >
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setError(null);
            saveMutation.mutate();
          }}
          className="space-y-4"
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="v-crop">Crop</Label>
              <Input
                id="v-crop"
                required
                value={form.crop}
                onChange={(e) => setForm({ ...form, crop: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="v-code">Code</Label>
              <Input
                id="v-code"
                required
                disabled={dialog !== "create"}
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
              />
            </div>
          </div>
          <div>
            <Label htmlFor="v-name">Name</Label>
            <Input
              id="v-name"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="v-mat">Maturity (days)</Label>
              <Input
                id="v-mat"
                type="number"
                min={1}
                max={400}
                value={form.maturityDays}
                onChange={(e) => setForm({ ...form, maturityDays: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="v-pot">Yield potential (kg/ha)</Label>
              <Input
                id="v-pot"
                type="number"
                min={1}
                value={form.yieldPotentialKgHa}
                onChange={(e) => setForm({ ...form, yieldPotentialKgHa: e.target.value })}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {(["droughtTolerance", "diseaseTolerance"] as const).map((key) => (
              <div key={key}>
                <Label htmlFor={`v-${key}`}>
                  {key === "droughtTolerance" ? "Drought tolerance" : "Disease tolerance"}
                </Label>
                <Select
                  id={`v-${key}`}
                  value={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                >
                  <option value="">—</option>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {n} / 5
                    </option>
                  ))}
                </Select>
              </div>
            ))}
          </div>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDialog(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saveMutation.isPending}>
              Save
            </Button>
          </div>
        </form>
      </Dialog>

      <Dialog
        open={suitabilityFor !== null}
        onClose={() => setSuitabilityFor(null)}
        title={`Region suitability — ${suitabilityFor?.name ?? ""}`}
      >
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setError(null);
            suitabilityMutation.mutate();
          }}
          className="space-y-4"
        >
          {(regions.data ?? []).length === 0 && (
            <p className="text-sm text-muted">Create regions first (Admin → Regions).</p>
          )}
          {(regions.data ?? []).map((region) => (
            <div key={region.id} className="flex items-center justify-between gap-4">
              <span className="text-sm">{region.name}</span>
              <Select
                aria-label={`Suitability for ${region.name}`}
                className="w-32"
                value={scores[region.id] ?? 0}
                onChange={(e) =>
                  setScores({ ...scores, [region.id]: Number(e.target.value) })
                }
              >
                <option value={0}>Not rated</option>
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n} / 5
                  </option>
                ))}
              </Select>
            </div>
          ))}
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setSuitabilityFor(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={suitabilityMutation.isPending}>
              Save matrix
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
