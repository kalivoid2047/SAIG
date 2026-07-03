import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { Region } from "@/lib/types";
import {
  Button,
  EmptyState,
  ErrorNote,
  Input,
  PageHeader,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";

export function RegionsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const regions = useQuery({
    queryKey: ["regions"],
    queryFn: () => api<Region[]>("/api/v1/regions"),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["regions"] });

  const createMutation = useMutation({
    mutationFn: () => api("/api/v1/regions", { method: "POST", body: { name, code } }),
    onSuccess: () => {
      setName("");
      setCode("");
      setError(null);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Request failed."),
  });

  const deleteMutation = useMutation({
    mutationFn: (region: Region) =>
      api(`/api/v1/regions/${region.id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });

  const data = regions.data ?? [];

  return (
    <div>
      <PageHeader
        title="Regions"
        description="Operating regions used for farmers, farms, forecasts and suitability."
      />

      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          createMutation.mutate();
        }}
        className="mb-4 flex max-w-lg gap-2"
      >
        <Input
          placeholder="Region name…"
          aria-label="Region name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Input
          placeholder="CODE"
          aria-label="Region code"
          required
          className="w-32 uppercase"
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
        <Button type="submit" disabled={createMutation.isPending}>
          Add
        </Button>
      </form>
      <div className="mb-4 max-w-lg">
        <ErrorNote message={error} />
      </div>

      {regions.isLoading && <Spinner />}
      {!regions.isLoading && data.length === 0 && (
        <EmptyState title="No regions yet" hint="Create the first operating region above." />
      )}
      {data.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Name</Th>
              <Th>Code</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {data.map((region) => (
              <tr key={region.id} className="hover:bg-elevated/40">
                <Td className="font-medium">{region.name}</Td>
                <Td className="font-mono text-xs">{region.code}</Td>
                <Td>
                  <div className="flex justify-end">
                    <Button
                      variant="ghost"
                      className="text-destructive"
                      onClick={() => {
                        if (confirm(`Delete region "${region.name}"?`)) {
                          deleteMutation.mutate(region);
                        }
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}
