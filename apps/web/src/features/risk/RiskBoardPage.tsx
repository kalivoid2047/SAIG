import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { api, ApiError } from "@/lib/api";
import type { JobResult, Region, RiskBoard, RiskDomain, RiskHistoryPoint } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { Badge, Button, Card, EmptyState, PageHeader, Select, Spinner } from "@/components/ui";

const DOMAIN_LABELS: Record<string, string> = {
  climate: "Climate",
  disease: "Disease",
  supply_chain: "Supply chain",
  inventory: "Inventory",
  production: "Production",
  financial: "Financial",
};

// Fixed 0–100 risk ramp (design-system): green → amber → red.
function bandColor(band: string): string {
  if (band === "high") return "hsl(0 72% 55%)";
  if (band === "medium") return "hsl(38 92% 55%)";
  return "hsl(152 65% 45%)";
}

function Gauge({ score, band }: { score: number; band: string }) {
  const color = bandColor(band);
  const angle = (score / 100) * 180;
  return (
    <div className="relative h-16 w-32">
      <svg viewBox="0 0 100 55" className="h-full w-full">
        <path d="M 8 50 A 42 42 0 0 1 92 50" fill="none" stroke="hsl(220 26% 18%)" strokeWidth="8" strokeLinecap="round" />
        <path
          d="M 8 50 A 42 42 0 0 1 92 50"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${(angle / 180) * 132} 132`}
        />
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <span className="text-2xl font-semibold tabular-nums" style={{ color }}>
          {score}
        </span>
      </div>
    </div>
  );
}

function TrendArrow({ trend }: { trend: number }) {
  if (trend === 0) return <span className="text-muted">▬ 0</span>;
  const up = trend > 0;
  return (
    <span className={up ? "text-destructive" : "text-success"}>
      {up ? "▲" : "▼"} {Math.abs(trend)}
    </span>
  );
}

function DomainCard({
  domain,
  regionId,
  expanded,
  onToggle,
}: {
  domain: RiskDomain;
  regionId: string | null;
  expanded: boolean;
  onToggle: () => void;
}) {
  const history = useQuery({
    queryKey: ["risk", "history", domain.domain, regionId],
    queryFn: () =>
      api<RiskHistoryPoint[]>("/api/v1/risks/history", {
        params: { domain: domain.domain, regionId: regionId ?? undefined, days: 90 },
      }),
    enabled: expanded,
  });

  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold">{DOMAIN_LABELS[domain.domain] ?? domain.domain}</h3>
          <div className="mt-1 flex items-center gap-2 text-xs">
            <Badge
              tone={domain.band === "high" ? "danger" : domain.band === "medium" ? "warning" : "success"}
            >
              {domain.band}
            </Badge>
            <TrendArrow trend={domain.trend} />
          </div>
        </div>
        <Gauge score={domain.score} band={domain.band} />
      </div>

      <button
        onClick={onToggle}
        className="mt-3 text-xs text-accent hover:underline"
        aria-expanded={expanded}
      >
        {expanded ? "Hide factors" : "Why?"}
      </button>

      {expanded && (
        <div className="mt-3 space-y-3 border-t border-border/60 pt-3">
          <div>
            <p className="mb-1 text-xs font-medium text-muted">Contributing factors</p>
            <ul className="space-y-1.5">
              {domain.factors.map((f) => (
                <li key={f.factor} className="text-xs">
                  <div className="flex justify-between">
                    <span className="text-muted">{f.factor.replace(/_/g, " ")}</span>
                    <span className="tabular-nums">+{f.contribution}</span>
                  </div>
                  <div className="mt-0.5 h-1 rounded bg-border">
                    <div
                      className="h-1 rounded"
                      style={{
                        width: `${Math.min((f.contribution / Math.max(domain.score, 1)) * 100, 100)}%`,
                        background: bandColor(domain.band),
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
          {history.data && history.data.length > 1 && (
            <div>
              <p className="mb-1 text-xs font-medium text-muted">90-day trend</p>
              <ResponsiveContainer width="100%" height={60}>
                <LineChart data={history.data}>
                  <YAxis domain={[0, 100]} hide />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(222 36% 13%)",
                      border: "1px solid hsl(220 26% 18%)",
                      borderRadius: 8,
                      fontSize: 11,
                    }}
                    labelFormatter={(l) => new Date(l).toLocaleDateString()}
                  />
                  <Line
                    dataKey="score"
                    stroke={bandColor(domain.band)}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export function RiskBoardPage() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [regionId, setRegionId] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const regions = useQuery({
    queryKey: ["regions"],
    queryFn: () => api<Region[]>("/api/v1/regions"),
  });
  const board = useQuery({
    queryKey: ["risk", "board", regionId],
    queryFn: () =>
      api<RiskBoard>("/api/v1/risks/board", {
        params: { regionId: regionId || undefined },
      }),
  });

  const recompute = useMutation({
    mutationFn: () => api<JobResult>("/api/v1/risks/recompute", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risk"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (err) => alert(err instanceof ApiError ? err.message : "Failed."),
  });

  return (
    <div>
      <PageHeader
        title="Risk board"
        description="Six-domain risk posture (0–100) derived from operational and predictive signals."
        actions={
          hasPermission("risks:compute") ? (
            <Button
              variant="secondary"
              onClick={() => recompute.mutate()}
              disabled={recompute.isPending}
            >
              {recompute.isPending ? "Recomputing…" : "Recompute"}
            </Button>
          ) : undefined
        }
      />

      <div className="mb-4 flex items-center gap-3">
        <div className="w-56">
          <Select aria-label="Scope" value={regionId} onChange={(e) => setRegionId(e.target.value)}>
            <option value="">Organization-wide</option>
            {(regions.data ?? []).map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </Select>
        </div>
        {board.data?.assessedDate && (
          <span className="text-xs text-muted">
            as of {new Date(board.data.assessedDate).toLocaleDateString()}
            {board.data.highRiskCount > 0 && (
              <>
                {" · "}
                <span className="text-destructive">{board.data.highRiskCount} high</span>
              </>
            )}
          </span>
        )}
      </div>

      {board.isLoading && <Spinner />}
      {board.data && board.data.domains.length === 0 && (
        <EmptyState
          title="No risk assessment yet"
          hint={
            hasPermission("risks:compute")
              ? "Click Recompute to score the six risk domains."
              : "Ask an analyst to run a risk recomputation."
          }
        />
      )}
      {board.data && board.data.domains.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {board.data.domains.map((d) => (
            <DomainCard
              key={d.domain}
              domain={d}
              regionId={regionId || null}
              expanded={expanded === d.domain}
              onToggle={() => setExpanded(expanded === d.domain ? null : d.domain)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
