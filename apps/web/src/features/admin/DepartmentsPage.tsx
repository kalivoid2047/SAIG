import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { Department } from "@/lib/types";
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

export function DepartmentsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const departmentsQuery = useQuery({
    queryKey: ["departments"],
    queryFn: () => api<Department[]>("/api/v1/departments"),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["departments"] });

  const createMutation = useMutation({
    mutationFn: () => api("/api/v1/departments", { method: "POST", body: { name } }),
    onSuccess: () => {
      setName("");
      setError(null);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Request failed. Try again."),
  });

  const deleteMutation = useMutation({
    mutationFn: (dept: Department) =>
      api(`/api/v1/departments/${dept.id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    createMutation.mutate();
  }

  const departments = departmentsQuery.data ?? [];

  return (
    <div>
      <PageHeader
        title="Departments"
        description="Organizational units users can belong to."
      />

      <form onSubmit={onSubmit} className="mb-4 flex max-w-md gap-2">
        <Input
          placeholder="New department name…"
          aria-label="New department name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Button type="submit" disabled={createMutation.isPending}>
          Add
        </Button>
      </form>
      <div className="mb-4 max-w-md">
        <ErrorNote message={error} />
      </div>

      {departmentsQuery.isLoading && <Spinner />}
      {!departmentsQuery.isLoading && departments.length === 0 && (
        <EmptyState title="No departments yet" hint="Create the first one above." />
      )}
      {departments.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Name</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {departments.map((dept) => (
              <tr key={dept.id} className="hover:bg-elevated/40">
                <Td className="font-medium">{dept.name}</Td>
                <Td>
                  <div className="flex justify-end">
                    <Button
                      variant="ghost"
                      className="text-destructive"
                      onClick={() => {
                        if (confirm(`Delete department "${dept.name}"?`)) {
                          deleteMutation.mutate(dept);
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
