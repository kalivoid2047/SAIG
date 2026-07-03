import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { Disease, DiseaseReport, Page } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import {
  Badge,
  Button,
  EmptyState,
  PageHeader,
  Pagination,
  Select,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";

const STATUS_TONES: Record<DiseaseReport["status"], "neutral" | "accent" | "warning" | "success" | "danger"> = {
  reported: "warning",
  confirmed: "accent",
  treated: "accent",
  resolved: "success",
  dismissed: "neutral",
};

const NEXT: Record<DiseaseReport["status"], DiseaseReport["status"][]> = {
  reported: ["confirmed", "dismissed"],
  confirmed: ["treated", "dismissed"],
  treated: ["resolved", "dismissed"],
  resolved: [],
  dismissed: [],
};

export function DiseaseReportsPage() {
  const { hasPermission } = useAuth();
  const canConfirm = hasPermission("crops:confirm");
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");

  const reports = useQuery({
    queryKey: ["disease-reports", page, status],
    queryFn: () =>
      api<Page<DiseaseReport>>("/api/v1/disease-reports", {
        params: { page, pageSize: 15, status: status || undefined },
      }),
  });
  const diseases = useQuery({
    queryKey: ["diseases"],
    queryFn: () => api<Disease[]>("/api/v1/diseases"),
  });

  const diseaseName = (id: string | null) =>
    id ? (diseases.data?.find((d) => d.id === id)?.name ?? "—") : "Unidentified";

  const transition = useMutation({
    mutationFn: ({ id, to }: { id: string; to: string }) =>
      api(`/api/v1/disease-reports/${id}/transitions`, { method: "POST", body: { to } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["disease-reports"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (err) => alert(err instanceof ApiError ? err.message : "Failed."),
  });

  const data = reports.data;

  return (
    <div>
      <PageHeader
        title="Disease reports"
        description="Field-reported crop disease with automatic outbreak detection (≥3 within 10 km / 7 days)."
      />

      <div className="mb-4 w-48">
        <Select
          aria-label="Filter by status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          {["reported", "confirmed", "treated", "resolved", "dismissed"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
      </div>

      {reports.isLoading && <Spinner />}
      {data && data.data.length === 0 && <EmptyState title="No disease reports match" />}
      {data && data.data.length > 0 && (
        <>
          <Table>
            <thead>
              <tr>
                <Th>Reported</Th>
                <Th>Disease</Th>
                <Th>Severity</Th>
                <Th>Affected</Th>
                <Th>Status</Th>
                <Th>Location</Th>
                {canConfirm && <Th />}
              </tr>
            </thead>
            <tbody>
              {data.data.map((r) => (
                <tr key={r.id} className="hover:bg-elevated/40">
                  <Td className="tabular-nums text-muted">
                    {new Date(r.reportedAt).toLocaleDateString()}
                  </Td>
                  <Td className="font-medium">
                    {diseaseName(r.diseaseId)}
                    {r.isOutbreak && <Badge tone="danger">outbreak</Badge>}
                  </Td>
                  <Td className="tabular-nums">{"●".repeat(r.severity)}{"○".repeat(5 - r.severity)}</Td>
                  <Td className="tabular-nums">{r.affectedPct}%</Td>
                  <Td>
                    <Badge tone={STATUS_TONES[r.status]}>{r.status}</Badge>
                  </Td>
                  <Td className="font-mono text-xs text-muted">
                    {r.latitude.toFixed(3)}, {r.longitude.toFixed(3)}
                  </Td>
                  {canConfirm && (
                    <Td>
                      <div className="flex justify-end gap-1">
                        {NEXT[r.status].map((to) => (
                          <Button
                            key={to}
                            variant="ghost"
                            className="px-2 py-0.5 text-xs"
                            onClick={() => transition.mutate({ id: r.id, to })}
                          >
                            → {to}
                          </Button>
                        ))}
                      </div>
                    </Td>
                  )}
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination page={page} totalPages={data.meta.totalPages} onPage={setPage} />
        </>
      )}
    </div>
  );
}
