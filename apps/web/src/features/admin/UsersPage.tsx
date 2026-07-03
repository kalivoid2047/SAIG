import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { Department, Page, Role, User } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import {
  Badge,
  Button,
  Dialog,
  EmptyState,
  ErrorNote,
  FieldError,
  Input,
  Label,
  PageHeader,
  Pagination,
  Select,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";

interface UserForm {
  email: string;
  password: string;
  fullName: string;
  departmentId: string;
  roleIds: string[];
}

const EMPTY_FORM: UserForm = { email: "", password: "", fullName: "", departmentId: "", roleIds: [] };

export function UsersPage() {
  const { user: me, hasPermission } = useAuth();
  const canManage = hasPermission("users:manage");
  const queryClient = useQueryClient();

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [dialog, setDialog] = useState<"create" | User | null>(null);
  const [form, setForm] = useState<UserForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const usersQuery = useQuery({
    queryKey: ["users", page, search],
    queryFn: () =>
      api<Page<User>>("/api/v1/users", { params: { page, pageSize: 10, search } }),
  });
  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => api<Role[]>("/api/v1/roles"),
  });
  const departmentsQuery = useQuery({
    queryKey: ["departments"],
    queryFn: () => api<Department[]>("/api/v1/departments"),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["users"] });

  function openCreate() {
    setForm(EMPTY_FORM);
    setError(null);
    setFieldErrors({});
    setDialog("create");
  }

  function openEdit(user: User) {
    setForm({
      email: user.email,
      password: "",
      fullName: user.fullName,
      departmentId: user.departmentId ?? "",
      roleIds: user.roles.map((r) => r.id),
    });
    setError(null);
    setFieldErrors({});
    setDialog(user);
  }

  function handleApiError(err: unknown) {
    if (err instanceof ApiError) {
      setError(err.message);
      setFieldErrors(
        Object.fromEntries(err.fieldErrors.map((e) => [e.path, e.message])),
      );
    } else {
      setError("Request failed. Try again.");
    }
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (dialog === "create") {
        await api("/api/v1/users", {
          method: "POST",
          body: {
            email: form.email,
            password: form.password,
            fullName: form.fullName,
            departmentId: form.departmentId || null,
            roleIds: form.roleIds,
          },
        });
      } else if (dialog) {
        await api(`/api/v1/users/${dialog.id}`, {
          method: "PATCH",
          body: {
            fullName: form.fullName,
            ...(form.departmentId ? { departmentId: form.departmentId } : {}),
            roleIds: form.roleIds,
          },
        });
      }
    },
    onSuccess: () => {
      setDialog(null);
      invalidate();
    },
    onError: handleApiError,
  });

  const toggleActive = useMutation({
    mutationFn: (user: User) =>
      api(`/api/v1/users/${user.id}/${user.isActive ? "deactivate" : "activate"}`, {
        method: "POST",
      }),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (user: User) => api(`/api/v1/users/${user.id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    saveMutation.mutate();
  }

  const roleOptions = useMemo(() => rolesQuery.data ?? [], [rolesQuery.data]);
  const users = usersQuery.data;

  return (
    <div>
      <PageHeader
        title="Users"
        description="People with access to the platform, scoped to your organization."
        actions={canManage ? <Button onClick={openCreate}>+ New user</Button> : undefined}
      />

      <div className="mb-4 max-w-xs">
        <Input
          placeholder="Search name or email…"
          aria-label="Search users"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
      </div>

      {usersQuery.isLoading && <Spinner />}
      {users && users.data.length === 0 && (
        <EmptyState title="No users found" hint="Adjust the search or create a new user." />
      )}
      {users && users.data.length > 0 && (
        <>
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Email</Th>
                <Th>Roles</Th>
                <Th>Status</Th>
                <Th>Last login</Th>
                {canManage && <Th />}
              </tr>
            </thead>
            <tbody>
              {users.data.map((user) => (
                <tr key={user.id} className="hover:bg-elevated/40">
                  <Td className="font-medium">{user.fullName}</Td>
                  <Td className="text-muted">{user.email}</Td>
                  <Td>
                    <div className="flex flex-wrap gap-1">
                      {user.roles.map((r) => (
                        <Badge key={r.id}>{r.name}</Badge>
                      ))}
                    </div>
                  </Td>
                  <Td>
                    <Badge tone={user.isActive ? "success" : "danger"}>
                      {user.isActive ? "Active" : "Inactive"}
                    </Badge>
                  </Td>
                  <Td className="tabular-nums text-muted">
                    {user.lastLoginAt ? new Date(user.lastLoginAt).toLocaleString() : "—"}
                  </Td>
                  {canManage && (
                    <Td>
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" onClick={() => openEdit(user)}>
                          Edit
                        </Button>
                        {user.id !== me?.id && (
                          <>
                            <Button variant="ghost" onClick={() => toggleActive.mutate(user)}>
                              {user.isActive ? "Deactivate" : "Activate"}
                            </Button>
                            <Button
                              variant="ghost"
                              className="text-destructive"
                              onClick={() => {
                                if (confirm(`Delete ${user.fullName}? This cannot be undone.`)) {
                                  deleteMutation.mutate(user);
                                }
                              }}
                            >
                              Delete
                            </Button>
                          </>
                        )}
                      </div>
                    </Td>
                  )}
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination page={page} totalPages={users.meta.totalPages} onPage={setPage} />
        </>
      )}

      <Dialog
        open={dialog !== null}
        onClose={() => setDialog(null)}
        title={dialog === "create" ? "New user" : "Edit user"}
      >
        <form onSubmit={onSubmit} className="space-y-4">
          {dialog === "create" && (
            <>
              <div>
                <Label htmlFor="u-email">Email</Label>
                <Input
                  id="u-email"
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
                <FieldError message={fieldErrors["email"]} />
              </div>
              <div>
                <Label htmlFor="u-password">Temporary password (min 10 chars)</Label>
                <Input
                  id="u-password"
                  type="password"
                  required
                  minLength={10}
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                />
                <FieldError message={fieldErrors["password"]} />
              </div>
            </>
          )}
          <div>
            <Label htmlFor="u-name">Full name</Label>
            <Input
              id="u-name"
              required
              value={form.fullName}
              onChange={(e) => setForm({ ...form, fullName: e.target.value })}
            />
            <FieldError message={fieldErrors["fullName"]} />
          </div>
          <div>
            <Label htmlFor="u-dept">Department</Label>
            <Select
              id="u-dept"
              value={form.departmentId}
              onChange={(e) => setForm({ ...form, departmentId: e.target.value })}
            >
              <option value="">— None —</option>
              {(departmentsQuery.data ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
          </div>
          <fieldset>
            <legend className="mb-1 block text-xs font-medium text-muted">Roles</legend>
            <div className="space-y-1.5">
              {roleOptions.map((role) => (
                <label key={role.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.roleIds.includes(role.id)}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        roleIds: e.target.checked
                          ? [...form.roleIds, role.id]
                          : form.roleIds.filter((id) => id !== role.id),
                      })
                    }
                  />
                  {role.name}
                  {role.isSystem && <Badge>system</Badge>}
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
