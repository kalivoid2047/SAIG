import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "@/lib/api";
import type { DiseaseFeatureCollection, FarmFeatureCollection, Region } from "@/lib/types";
import { Card, PageHeader, Spinner } from "@/components/ui";

const KENYA_CENTER: [number, number] = [-0.2, 36.5];

// Fixed severity ramp (design-system: warning → danger)
function severityColor(severity: number): string {
  if (severity >= 4) return "hsl(0 72% 55%)";
  if (severity >= 3) return "hsl(38 92% 55%)";
  return "hsl(199 90% 55%)";
}

export function MapPage() {
  const [showFarms, setShowFarms] = useState(true);
  const [showDisease, setShowDisease] = useState(true);

  const farms = useQuery({
    queryKey: ["gis", "farms"],
    queryFn: () => api<FarmFeatureCollection>("/api/v1/gis/farms"),
  });
  const disease = useQuery({
    queryKey: ["gis", "disease"],
    queryFn: () => api<DiseaseFeatureCollection>("/api/v1/gis/disease-heatmap"),
  });
  const regions = useQuery({
    queryKey: ["regions"],
    queryFn: () => api<Region[]>("/api/v1/regions"),
  });
  const regionName = (id: string | null) =>
    regions.data?.find((r) => r.id === id)?.name ?? "Unassigned";

  const outbreaks = disease.data?.features.filter((f) => f.properties.isOutbreak).length ?? 0;

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Farm map"
        description={
          farms.data
            ? `${farms.data.features.length} farms · ${disease.data?.features.length ?? 0} active disease reports${outbreaks ? ` · ${outbreaks} in outbreaks` : ""}`
            : undefined
        }
      />

      <div className="mb-3 flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showFarms} onChange={(e) => setShowFarms(e.target.checked)} />
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full" style={{ background: "hsl(152 65% 45%)" }} />
            Farms
          </span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showDisease}
            onChange={(e) => setShowDisease(e.target.checked)}
          />
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full" style={{ background: "hsl(0 72% 55%)" }} />
            Disease reports
          </span>
        </label>
      </div>

      {(farms.isLoading || disease.isLoading) && <Spinner label="Loading map layers…" />}
      {farms.data && (
        <div className="min-h-[460px] flex-1 overflow-hidden rounded-[10px] border border-border">
          <MapContainer center={KENYA_CENTER} zoom={7} className="h-full w-full" style={{ background: "#0a0f1e" }}>
            <TileLayer
              attribution='&copy; OpenStreetMap &copy; CARTO'
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />

            {showFarms &&
              farms.data.features.map((f) => {
                const [lng, lat] = f.geometry.coordinates;
                const p = f.properties;
                return (
                  <CircleMarker
                    key={p.id}
                    center={[lat, lng]}
                    radius={6}
                    pathOptions={{
                      color: "hsl(152 65% 45%)",
                      fillColor: "hsl(152 65% 45%)",
                      fillOpacity: 0.5,
                      weight: 1.5,
                    }}
                  >
                    <Popup>
                      <div style={{ fontSize: 13, lineHeight: 1.5 }}>
                        <strong>{p.name}</strong>
                        <br />
                        Farmer:{" "}
                        {p.farmerName ? (
                          <Link to={`/farmers/${p.farmerId}`}>{p.farmerName}</Link>
                        ) : (
                          "—"
                        )}
                        <br />
                        Region: {regionName(p.regionId)} · Fields: {p.fieldCount}
                      </div>
                    </Popup>
                  </CircleMarker>
                );
              })}

            {showDisease &&
              disease.data?.features.map((f) => {
                const [lng, lat] = f.geometry.coordinates;
                const p = f.properties;
                return (
                  <CircleMarker
                    key={p.id}
                    center={[lat, lng]}
                    radius={p.isOutbreak ? 12 : 6 + p.severity}
                    pathOptions={{
                      color: severityColor(p.severity),
                      fillColor: severityColor(p.severity),
                      fillOpacity: p.isOutbreak ? 0.45 : 0.3,
                      weight: p.isOutbreak ? 2 : 1,
                    }}
                  >
                    <Popup>
                      <div style={{ fontSize: 13, lineHeight: 1.5 }}>
                        <strong>Disease report</strong>
                        {p.isOutbreak && <span style={{ color: "#dc2626" }}> · OUTBREAK</span>}
                        <br />
                        Severity: {p.severity}/5 · {p.affectedPct}% affected
                        <br />
                        Status: {p.status}
                      </div>
                    </Popup>
                  </CircleMarker>
                );
              })}
          </MapContainer>
        </div>
      )}

      {outbreaks > 0 && (
        <Card className="mt-3 border-destructive/40">
          <p className="text-sm">
            <span className="font-semibold text-destructive">{outbreaks}</span> disease report
            {outbreaks === 1 ? "" : "s"} flagged as part of an active outbreak cluster.
          </p>
        </Card>
      )}
    </div>
  );
}
