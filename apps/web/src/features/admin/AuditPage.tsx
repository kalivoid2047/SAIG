import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AuditLog, Page } from "@/lib/types";
import {
  Badge,
  EmptyState,
  Input,
  PageHeader,
  Pagination,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";

function actionTone(action: string): "neutral" | "warning" | "danger" | "accent" {
  if (action.includes("delete") || action.includes("lockout") || action.includes("reuse")) {
    return "danger";
  }
  if (action.includes("deactivate")) return "warning";
  if (action.startsWith("auth.")) return "accent";
  return "neutral";
}

export function AuditPage() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");

  const logsQuery = useQuery({
    queryKey: ["audit-logs", page, action],
    queryFn: () =>
      api<Page<AuditLog>>("/api/v1/audit-logs", {
        params: { page, pageSize: 20, action: action || undefined },
      }),
  });

  const logs = logsQuery.data;

  return (
    <div>
      <PageHeader
        title="Audit log"
        description="Immutable record of security-relevant actions in your organization."
      />

      <div className="mb-4 max-w-xs">
        <Input
          placeholder="Filter by exact action, e.g. auth.login"
          aria-label="Filter by action"
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(1);
          }}
        />
      </div>

      {logsQuery.isLoading && <Spinner />}
      {logs && logs.data.length === 0 && <EmptyState title="No audit entries match" />}
      {logs && logs.data.length > 0 && (
        <>
          <Table>
            <thead>
              <tr>
                <Th>When</Th>
                <Th>Action</Th>
                <Th>Entity</Th>
                <Th>Actor</Th>
                <Th>Request</Th>
              </tr>
            </thead>
            <tbody>
              {logs.data.map((log) => (
                <tr key={log.id} className="hover:bg-elevated/40">
                  <Td className="whitespace-nowrap tabular-nums text-muted">
                    {new Date(log.occurredAt).toLocaleString()}
                  </Td>
                  <Td>
                    <Badge tone={actionTone(log.action)}>{log.action}</Badge>
                  </Td>
                  <Td className="text-muted">
                    {log.entityTable ? (
                      <span className="font-mono text-xs">
                        {log.entityTable}
                        {log.entityId ? ` · ${log.entityId.slice(0, 8)}…` : ""}
                      </span>
                    ) : (
                      "—"
                    )}
                  </Td>
                  <Td className="font-mono text-xs text-muted">
                    {log.actorId ? `${log.actorId.slice(0, 8)}…` : "system"}
                  </Td>
                  <Td className="font-mono text-xs text-muted">{log.requestId ?? "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination page={page} totalPages={logs.meta.totalPages} onPage={setPage} />
        </>
      )}
    </div>
  );
}
