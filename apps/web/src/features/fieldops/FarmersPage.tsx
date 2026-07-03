import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { Farmer, Page, Region } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import {
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

interface FarmerForm {
  fullName: string;
  phone: string;
  nationalId: string;
  gender: string;
  cooperative: string;
  regionId: string;
  consentGiven: boolean;
}

const EMPTY: FarmerForm = {
  fullName: "",
  phone: "",
  nationalId: "",
  gender: "",
  cooperative: "",
  regionId: "",
  consentGiven: false,
};

export function FarmersPage() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FarmerForm>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const regions = useQuery({
    queryKey: ["regions"],
    queryFn: () => api<Region[]>("/api/v1/regions"),
  });
  const farmers = useQuery({
    queryKey: ["farmers", page, search, regionFilter],
    queryFn: () =>
      api<Page<Farmer>>("/api/v1/farmers", {
        params: { page, pageSize: 10, search, regionId: regionFilter || undefined },
      }),
  });

  const regionName = (id: string | null) =>
    regions.data?.find((r) => r.id === id)?.name ?? "—";

  const createMutation = useMutation({
    mutationFn: () =>
      api("/api/v1/farmers", {
        method: "POST",
        body: {
          fullName: form.fullName,
          phone: form.phone || null,
          nationalId: form.nationalId || null,
          gender: form.gender || null,
          cooperative: form.cooperative || null,
          regionId: form.regionId || null,
          consentGiven: form.consentGiven,
        },
      }),
    onSuccess: () => {
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["farmers"] });
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setError(err.message);
        setFieldErrors(Object.fromEntries(err.fieldErrors.map((e) => [e.path, e.message])));
      } else {
        setError("Registration failed. Try again.");
      }
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setFieldErrors({});
    createMutation.mutate();
  }

  const data = farmers.data;

  return (
    <div>
      <PageHeader
        title="Farmers"
        description="Registered growers. Personal data is masked unless you hold the PII permission."
        actions={
          hasPermission("farmers:create") ? (
            <Button
              onClick={() => {
                setForm(EMPTY);
                setError(null);
                setFieldErrors({});
                setOpen(true);
              }}
            >
              + Register farmer
            </Button>
          ) : undefined
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <div className="w-64">
          <Input
            placeholder="Search by name…"
            aria-label="Search farmers"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <div className="w-48">
          <Select
            aria-label="Filter by region"
            value={regionFilter}
            onChange={(e) => {
              setRegionFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All regions</option>
            {(regions.data ?? []).map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {farmers.isLoading && <Spinner />}
      {data && data.data.length === 0 && (
        <EmptyState title="No farmers found" hint="Register the first farmer to get started." />
      )}
      {data && data.data.length > 0 && (
        <>
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Phone</Th>
                <Th>Region</Th>
                <Th>Cooperative</Th>
                <Th>Farms</Th>
                <Th>Registered</Th>
              </tr>
            </thead>
            <tbody>
              {data.data.map((farmer) => (
                <tr key={farmer.id} className="hover:bg-elevated/40">
                  <Td className="font-medium">
                    <Link to={`/farmers/${farmer.id}`} className="text-accent hover:underline">
                      {farmer.fullName}
                    </Link>
                  </Td>
                  <Td className="tabular-nums text-muted">{farmer.phone ?? "—"}</Td>
                  <Td className="text-muted">{regionName(farmer.regionId)}</Td>
                  <Td className="text-muted">{farmer.cooperative ?? "—"}</Td>
                  <Td className="tabular-nums">{farmer.farmCount}</Td>
                  <Td className="tabular-nums text-muted">
                    {new Date(farmer.createdAt).toLocaleDateString()}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pagination page={page} totalPages={data.meta.totalPages} onPage={setPage} />
        </>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} title="Register farmer">
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <Label htmlFor="f-name">Full name</Label>
            <Input
              id="f-name"
              required
              value={form.fullName}
              onChange={(e) => setForm({ ...form, fullName: e.target.value })}
            />
            <FieldError message={fieldErrors["fullName"]} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="f-phone">Phone</Label>
              <Input
                id="f-phone"
                placeholder="+2547…"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
              <FieldError message={fieldErrors["phone"]} />
            </div>
            <div>
              <Label htmlFor="f-nid">National ID</Label>
              <Input
                id="f-nid"
                value={form.nationalId}
                onChange={(e) => setForm({ ...form, nationalId: e.target.value })}
              />
              <FieldError message={fieldErrors["nationalId"]} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="f-region">Region</Label>
              <Select
                id="f-region"
                value={form.regionId}
                onChange={(e) => setForm({ ...form, regionId: e.target.value })}
              >
                <option value="">— None —</option>
                {(regions.data ?? []).map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="f-gender">Gender</Label>
              <Select
                id="f-gender"
                value={form.gender}
                onChange={(e) => setForm({ ...form, gender: e.target.value })}
              >
                <option value="">— Undisclosed —</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </Select>
            </div>
          </div>
          <div>
            <Label htmlFor="f-coop">Cooperative</Label>
            <Input
              id="f-coop"
              value={form.cooperative}
              onChange={(e) => setForm({ ...form, cooperative: e.target.value })}
            />
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              required
              checked={form.consentGiven}
              onChange={(e) => setForm({ ...form, consentGiven: e.target.checked })}
            />
            <span>
              The farmer has consented to SeedCo processing their personal data for
              agricultural services. <span className="text-destructive">*</span>
            </span>
          </label>
          <ErrorNote message={error} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Registering…" : "Register"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
