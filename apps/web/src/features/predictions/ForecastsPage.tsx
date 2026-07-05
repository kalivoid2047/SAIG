import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Area,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, ApiError } from "@/lib/api";
import type {
  DemandSeries,
  JobResult,
  ModelVersion,
  Region,
  Variety,
  YieldPrediction,
} from "@/lib/types";
import { useAuth } from "@/lib/auth";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  PageHeader,
  Select,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";

type Tab = "demand" | "yield" | "models";

export function ForecastsPage() {
  const { hasPermission } = useAuth();
  const [tab, setTab] = useState<Tab>("demand");
  const canTrigger = hasPermission("forecasts:trigger");
  const tabs: { id: Tab; label: string }[] = [
    { id: "demand", label: "Demand forecast" },
    { id: "yield", label: "Yield predictions" },
    { id: "models", label: "Model registry" },
  ];

  return (
    <div>
      <PageHeader
        title="Forecasts"
        description="ML predictions with confidence — yield per crop cycle and 12-month demand by region and variety."
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

      {tab === "demand" && <DemandTab canTrigger={canTrigger} />}
      {tab === "yield" && <YieldTab canTrigger={canTrigger} />}
      {tab === "models" && <ModelsTab />}
    </div>
  );
}

function fmtKg(n: number): string {
  if (n >= 1000) return `${(n / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })} t`;
  return `${Math.round(n).toLocaleString()} kg`;
}

// --- Demand ------------------------------------------------------------------

function DemandTab({ canTrigger }: { canTrigger: boolean }) {
  const queryClient = useQueryClient();
  const [regionId, setRegionId] = useState("");
  const [varietyId, setVarietyId] = useState("");

  const regions = useQuery({
    queryKey: ["regions"],
    queryFn: () => api<Region[]>("/api/v1/regions"),
  });
  const varieties = useQuery({
    queryKey: ["varieties"],
    queryFn: () => api<Variety[]>("/api/v1/varieties"),
  });

  useEffect(() => {
    if (!regionId && regions.data?.length) setRegionId(regions.data[0]!.id);
  }, [regions.data, regionId]);
  useEffect(() => {
    if (!varietyId && varieties.data?.length) setVarietyId(varieties.data[0]!.id);
  }, [varieties.data, varietyId]);

  const series = useQuery({
    queryKey: ["forecast", "demand", regionId, varietyId],
    queryFn: () =>
      api<DemandSeries>("/api/v1/forecasts/demand", {
        params: { regionId, varietyId },
      }),
    enabled: Boolean(regionId && varietyId),
    retry: false,
  });

  const run = useMutation({
    mutationFn: () => api<JobResult>("/api/v1/forecasts/demand/run", { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["forecast", "demand"] }),
    onError: (err) => alert(err instanceof ApiError ? err.message : "Failed."),
  });

  const chartData =
    series.data?.points.map((p) => ({
      month: p.periodMonth.slice(0, 7),
      forecast: p.forecastQtyKg,
      low: p.piLowKg,
      band: p.piHighKg - p.piLowKg,
      confidence: p.confidence,
    })) ?? [];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-2">
        <div className="w-48">
          <Select aria-label="Region" value={regionId} onChange={(e) => setRegionId(e.target.value)}>
            {(regions.data ?? []).map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-56">
          <Select aria-label="Variety" value={varietyId} onChange={(e) => setVarietyId(e.target.value)}>
            {(varieties.data ?? []).map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} ({v.code})
              </option>
            ))}
          </Select>
        </div>
        {canTrigger && (
          <Button variant="secondary" onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending ? "Running…" : "Regenerate forecasts"}
          </Button>
        )}
      </div>

      {series.isLoading && <Spinner label="Loading forecast…" />}
      {series.isError && (
        <EmptyState
          title="No forecast yet for this segment"
          hint={
            canTrigger
              ? "Click “Regenerate forecasts” to run the demand model."
              : "Ask an analyst to run the demand model."
          }
        />
      )}
      {series.data && chartData.length > 0 && (
        <Card>
          <h3 className="mb-4 text-sm font-semibold">
            12-month demand forecast{" "}
            <span className="text-muted">· 80% interval</span>
          </h3>
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
              <XAxis dataKey="month" tick={{ fill: "hsl(215 16% 62%)", fontSize: 11 }} />
              <YAxis
                tick={{ fill: "hsl(215 16% 62%)", fontSize: 11 }}
                tickFormatter={(v) => `${Math.round(v / 1000)}t`}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(222 36% 13%)",
                  border: "1px solid hsl(220 26% 18%)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value: number, name: string) =>
                  name === "band" ? null : [fmtKg(value), name]
                }
              />
              {/* Interval band: transparent base + shaded height */}
              <Area dataKey="low" stackId="ci" stroke="none" fill="transparent" isAnimationActive={false} />
              <Area
                dataKey="band"
                stackId="ci"
                stroke="none"
                fill="hsl(199 90% 55%)"
                fillOpacity={0.15}
                isAnimationActive={false}
              />
              <Line
                dataKey="forecast"
                stroke="hsl(152 65% 45%)"
                strokeWidth={2}
                dot={{ r: 2 }}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
          <p className="mt-2 text-xs text-muted">
            Model: {series.data.modelVersion} · avg confidence{" "}
            {(
              (chartData.reduce((s, d) => s + d.confidence, 0) / chartData.length) *
              100
            ).toFixed(0)}
            %
          </p>
        </Card>
      )}
    </div>
  );
}

// --- Yield -------------------------------------------------------------------

function confidenceDots(c: number): string {
  const filled = Math.round(c * 5);
  return "●".repeat(filled) + "○".repeat(5 - filled);
}

function YieldTab({ canTrigger }: { canTrigger: boolean }) {
  const queryClient = useQueryClient();
  const predictions = useQuery({
    queryKey: ["predictions", "yield"],
    queryFn: () => api<YieldPrediction[]>("/api/v1/predictions/yield"),
  });

  const rescore = useMutation({
    mutationFn: () =>
      api<JobResult>("/api/v1/predictions/yield/rescore", { method: "POST", body: {} }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["predictions", "yield"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (err) => alert(err instanceof ApiError ? err.message : "Failed."),
  });

  const data = predictions.data ?? [];

  return (
    <div>
      {canTrigger && (
        <div className="mb-4">
          <Button variant="secondary" onClick={() => rescore.mutate()} disabled={rescore.isPending}>
            {rescore.isPending ? "Scoring…" : "Re-score active crop cycles"}
          </Button>
        </div>
      )}
      {predictions.isLoading && <Spinner />}
      {!predictions.isLoading && data.length === 0 && (
        <EmptyState
          title="No yield predictions yet"
          hint={canTrigger ? "Re-score active crop cycles to generate predictions." : undefined}
        />
      )}
      {data.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Crop cycle</Th>
              <Th>Predicted yield</Th>
              <Th>80% interval</Th>
              <Th>Confidence</Th>
              <Th>As of</Th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={p.id} className="hover:bg-elevated/40">
                <Td className="font-mono text-xs">{p.cropCycleId.slice(0, 8)}</Td>
                <Td className="tabular-nums font-medium">
                  {p.predictedYieldKgHa.toLocaleString()} kg/ha
                </Td>
                <Td className="tabular-nums text-muted">
                  {Math.round(p.piLowKgHa).toLocaleString()}–
                  {Math.round(p.piHighKgHa).toLocaleString()}
                </Td>
                <Td>
                  <span className="tabular-nums">{confidenceDots(p.confidence)}</span>{" "}
                  {p.lowConfidence && <Badge tone="warning">low</Badge>}
                </Td>
                <Td className="tabular-nums text-muted">
                  {new Date(p.createdAt).toLocaleDateString()}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}

// --- Models ------------------------------------------------------------------

function ModelsTab() {
  const { hasPermission } = useAuth();
  const models = useQuery({
    queryKey: ["models"],
    queryFn: () => api<ModelVersion[]>("/api/v1/models"),
    enabled: hasPermission("models:read"),
  });

  if (!hasPermission("models:read")) {
    return <EmptyState title="You don't have access to the model registry" />;
  }

  const tones = {
    promoted: "success",
    trained: "accent",
    evaluated: "accent",
    retired: "neutral",
  } as const;

  return (
    <div>
      {models.isLoading && <Spinner />}
      {models.data && models.data.length === 0 && (
        <EmptyState title="No models trained yet" hint="Run python -m saig.scripts.train_models" />
      )}
      {models.data && models.data.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Model</Th>
              <Th>Version</Th>
              <Th>Status</Th>
              <Th>Metrics</Th>
              <Th>Training rows</Th>
              <Th>Created</Th>
            </tr>
          </thead>
          <tbody>
            {models.data.map((m) => (
              <tr key={m.id} className="hover:bg-elevated/40">
                <Td className="font-medium capitalize">{m.modelName}</Td>
                <Td className="font-mono text-xs">{m.version}</Td>
                <Td>
                  <Badge tone={tones[m.status]}>{m.status}</Badge>
                </Td>
                <Td className="text-xs text-muted">
                  {Object.entries(m.metrics)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(" · ")}
                </Td>
                <Td className="tabular-nums text-muted">{m.trainingRows ?? "—"}</Td>
                <Td className="tabular-nums text-muted">
                  {new Date(m.createdAt).toLocaleDateString()}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}
