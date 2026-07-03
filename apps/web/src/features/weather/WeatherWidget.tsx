import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AgroIndicators, WeatherForecast } from "@/lib/types";
import { Badge, Card, Spinner } from "@/components/ui";

/** Compact weather panel for a farm — 7-day forecast + agro-indicators. */
export function WeatherWidget({ farmId }: { farmId: string }) {
  const forecast = useQuery({
    queryKey: ["weather", "forecast", farmId],
    queryFn: () =>
      api<WeatherForecast>("/api/v1/weather/forecast", { params: { farmId, days: 7 } }),
  });
  const agro = useQuery({
    queryKey: ["weather", "agro", farmId],
    queryFn: () =>
      api<AgroIndicators>("/api/v1/weather/aggregates", { params: { farmId, window: 90 } }),
  });

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Weather</h3>
        {forecast.data && (
          <Badge tone={forecast.data.stale ? "warning" : "neutral"}>
            {forecast.data.source}
            {forecast.data.stale ? " · stale" : ""}
          </Badge>
        )}
      </div>

      {(forecast.isLoading || agro.isLoading) && <Spinner label="Fetching weather…" />}

      {forecast.data && (
        <div className="mb-4 flex gap-2 overflow-x-auto">
          {forecast.data.days.map((d) => (
            <div
              key={d.day}
              className="flex min-w-[64px] flex-col items-center rounded-md border border-border/60 p-2 text-center"
            >
              <span className="text-[10px] text-muted">
                {new Date(d.day).toLocaleDateString(undefined, { weekday: "short" })}
              </span>
              <span className="mt-1 text-sm font-semibold tabular-nums">
                {d.tempMaxC != null ? Math.round(d.tempMaxC) : "—"}°
              </span>
              <span className="text-[10px] tabular-nums text-muted">
                {d.tempMinC != null ? Math.round(d.tempMinC) : "—"}°
              </span>
              <span className="mt-1 text-[10px] tabular-nums text-accent">
                {d.rainfallMm != null ? `${d.rainfallMm}mm` : ""}
              </span>
            </div>
          ))}
        </div>
      )}

      {agro.data && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
          <dt className="text-muted">Rain (30d)</dt>
          <dd className="text-right tabular-nums">
            {agro.data.rainfall30dMm != null ? `${agro.data.rainfall30dMm} mm` : "—"}
          </dd>
          <dt className="text-muted">Rain (90d)</dt>
          <dd className="text-right tabular-nums">
            {agro.data.rainfall90dMm != null ? `${agro.data.rainfall90dMm} mm` : "—"}
          </dd>
          <dt className="text-muted">Growing degree days</dt>
          <dd className="text-right tabular-nums">
            {agro.data.growingDegreeDays != null ? agro.data.growingDegreeDays : "—"}
          </dd>
          <dt className="text-muted">Heat-stress days</dt>
          <dd className="text-right tabular-nums">
            {agro.data.heatStressDays > 0 ? (
              <Badge tone="warning">{agro.data.heatStressDays}</Badge>
            ) : (
              agro.data.heatStressDays
            )}
          </dd>
        </dl>
      )}
    </Card>
  );
}
