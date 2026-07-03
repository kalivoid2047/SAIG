import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "@/lib/api";
import type { FarmFeatureCollection, Region } from "@/lib/types";
import { PageHeader, Spinner } from "@/components/ui";

const KENYA_CENTER: [number, number] = [-0.2, 36.5];

export function MapPage() {
  const farms = useQuery({
    queryKey: ["gis", "farms"],
    queryFn: () => api<FarmFeatureCollection>("/api/v1/gis/farms"),
  });
  const regions = useQuery({
    queryKey: ["regions"],
    queryFn: () => api<Region[]>("/api/v1/regions"),
  });

  const regionName = (id: string | null) =>
    regions.data?.find((r) => r.id === id)?.name ?? "Unassigned";

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Farm map"
        description={
          farms.data
            ? `${farms.data.features.length} farm location${farms.data.features.length === 1 ? "" : "s"} · GIS v1 (farm layer)`
            : undefined
        }
      />
      {farms.isLoading && <Spinner label="Loading farm locations…" />}
      {farms.data && (
        <div className="min-h-[480px] flex-1 overflow-hidden rounded-[10px] border border-border">
          <MapContainer
            center={KENYA_CENTER}
            zoom={7}
            className="h-full w-full"
            style={{ background: "#0a0f1e" }}
          >
            {/* Dark basemap to match the SAIG theme */}
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />
            {farms.data.features.map((feature) => {
              const [lng, lat] = feature.geometry.coordinates;
              const p = feature.properties;
              return (
                <CircleMarker
                  key={p.id}
                  center={[lat, lng]}
                  radius={7}
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
                      Region: {regionName(p.regionId)}
                      <br />
                      Fields: {p.fieldCount}
                      {p.totalAreaHa != null && (
                        <>
                          {" · "}
                          {p.totalAreaHa} ha
                        </>
                      )}
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        </div>
      )}
    </div>
  );
}
