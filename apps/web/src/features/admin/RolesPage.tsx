import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { Permission, Role } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  Dialog,
  ErrorNote,
  Input,
  Label,
  PageHeader,
  Spinner,
} from "@/components/ui";

interface RoleForm {
  name: string;
  description: string;
  permissionCodes: string[];
}

const EMPTY_FORM: RoleForm = { name: "", description: "", permissionCodes: [] };

export function RolesPage() {
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<"create" | Role | null>(null);
  const [form, setForm] = useState<RoleForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);

  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => api<Role[]>("/api/v1/roles"),
  });
  const permissionsQuery = useQuery({
    queryKey: ["permissions"],
    queryFn: () => api<Permission[]>("/api/v1/permissions"),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["roles"] });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const body = {
        name: form.name,
        description: form.description || null,
        permissionCodes: form.permissionCodes,
      };
      if (dialog === "create") {
        await api("/api/v1/roles", { method: "POST", body });
      } else if (dialog) {
        await api(`/api/v1/roles/${dialog.id}`, { method: "PATCH", body });
      }
    },
    onSuccess: () => {
      setDialog(null);
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Request failed. Try again."),
  });

  const deleteMutation = useMutation({
    mutationFn: (role: Role) => api(`/api/v1/roles/${role.id}`, { method: "DELETE" }),
    onSuccess: invalidate,
    onError: (err) =>
      alert(err instanceof ApiError ? err.message : "Could not delete role."),
  });

  function open(target: "create" | Role) {
    setError(null);
    if (target === "create") {
      setForm(EMPTY_FORM);
    } else {
      setForm({
        name: target.name,
        description: target.description ?? "",
        permissionCodes: target.permissions.map((p) => p.code),
      });
    }
    setDialog(target);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    saveMutation.mutate();
  }

  return (
    <div>
      <PageHeader
        title="Roles & permissions"
        description="Roles bundle permissions; users may hold multiple roles."
        actions={<Button onClick={() => open("create")}>+ New role</Button>}
      />

      {rolesQuery.isLoading && <Spinner />}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {(rolesQuery.data ?? []).map((role) => (
          <Card key={role.id}>
            <div className="flex items-start justify-between">
              <div>
                <h2 className="flex items-center gap-2 font-semibold">
                  {role.name}
                  {role.isSystem && <Badge tone="accent">system</Badge>}
                </h2>
                {role.description && (
                  <p className="mt-1 text-sm text-muted">{role.description}</p>
                )}
              </div>
              {!role.isSystem && (
                <div className="flex gap-1">
                  <Button variant="ghost" onClick={() => open(role)}>
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    className="text-destructive"
                    onClick={() => {
                      if (confirm(`Delete role "${role.name}"?`)) deleteMutation.mutate(role);
                    }}
                  >
                    Delete
                  </Button>
                </div>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {role.permissions.map((p) => (
                <Badge key={p.id}>{p.code}</Badge>
              ))}
              {role.permissions.length === 0 && (
                <p className="text-xs text-muted">No permissions.</p>
              )}
            </div>
          </Card>
        ))}
      </div>

      <Dialog
        open={dialog !== null}
        onClose={() => setDialog(null)}
        title={dialog === "create" ? "New role" : "Edit role"}
      >
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <Label htmlFor="r-name">Name</Label>
            <Input
              id="r-name"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="r-desc">Description</Label>
            <Input
              id="r-desc"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <fieldset>
            <legend className="mb-1 block text-xs font-medium text-muted">Permissions</legend>
            <div className="space-y-1.5">
              {(permissionsQuery.data ?? []).map((perm) => (
                <label key={perm.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.permissionCodes.includes(perm.code)}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        permissionCodes: e.target.checked
                          ? [...form.permissionCodes, perm.code]
                          : form.permissionCodes.filter((c) => c !== perm.code),
                      })
                    }
                  />
                  <span className="font-mono text-xs">{perm.code}</span>
                  <span className="text-muted">— {perm.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDialog(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
