"""Capacitated vehicle-routing optimization (FR-SC-4).

OR-Tools CVRP solver with a pure nearest-neighbour + greedy fallback, behind a
single `optimize` interface (same philosophy as ADR-0003: a solid solver with a
dependency-light fallback, both testable offline). Reports the optimized plan
and the distance saved versus a naive greedy first-fit baseline, so the value
of optimization is quantified rather than asserted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from saig.shared.geo import haversine_km

try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    _ORTOOLS = True
except ImportError:  # pragma: no cover - fallback path
    _ORTOOLS = False


@dataclass(frozen=True)
class Stop:
    order_id: str
    lat: float
    lng: float
    demand_kg: float


@dataclass
class OptimizedVehicleRoute:
    vehicle_index: int
    order_ids: list[str]
    distance_km: float


@dataclass
class OptimizationResult:
    routes: list[OptimizedVehicleRoute] = field(default_factory=list)
    total_distance_km: float = 0.0
    naive_distance_km: float = 0.0
    method: str = "none"

    @property
    def savings_pct(self) -> float:
        if self.naive_distance_km <= 0:
            return 0.0
        return round(
            max(0.0, (self.naive_distance_km - self.total_distance_km) / self.naive_distance_km)
            * 100.0,
            1,
        )


class InfeasibleRouteError(ValueError):
    """Raised when total demand cannot fit the available fleet capacity."""


def _distance_matrix(points: list[tuple[float, float]]) -> list[list[float]]:
    n = len(points)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine_km(points[i][0], points[i][1], points[j][0], points[j][1])
            matrix[i][j] = matrix[j][i] = d
    return matrix


def _route_distance(dist: list[list[float]], sequence: list[int]) -> float:
    """Depot (index 0) → stops in sequence, no return leg."""
    total = 0.0
    prev = 0
    for node in sequence:
        total += dist[prev][node]
        prev = node
    return total


def _naive_plan(
    dist: list[list[float]], stops: list[Stop], capacities: list[float]
) -> tuple[list[list[int]], float]:
    """Greedy first-fit: fill each vehicle in input order, sequence as given."""
    assignments: list[list[int]] = [[] for _ in capacities]
    loads = [0.0] * len(capacities)
    for node, stop in enumerate(stops, start=1):
        placed = False
        for v in range(len(capacities)):
            if loads[v] + stop.demand_kg <= capacities[v]:
                assignments[v].append(node)
                loads[v] += stop.demand_kg
                placed = True
                break
        if not placed:
            raise InfeasibleRouteError("Orders exceed total fleet capacity.")
    total = sum(_route_distance(dist, seq) for seq in assignments if seq)
    return assignments, total


def _two_opt(dist: list[list[float]], sequence: list[int]) -> list[int]:
    """Local-search improvement of a single vehicle's stop order."""
    if len(sequence) < 4:
        return sequence
    best = sequence[:]
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for k in range(i + 1, len(best)):
                candidate = best[:i] + best[i : k + 1][::-1] + best[k + 1 :]
                if _route_distance(dist, candidate) + 1e-9 < _route_distance(dist, best):
                    best = candidate
                    improved = True
    return best


def _solve_ortools(
    dist: list[list[float]], demands: list[float], capacities: list[float],
    time_limit_s: int = 3,
) -> list[list[int]] | None:  # pragma: no cover - exercised when ortools present
    n = len(dist)
    num_vehicles = len(capacities)
    manager = pywrapcp.RoutingIndexManager(n, num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    scale = 1000  # km → metres, integer costs

    def distance_cb(from_index: int, to_index: int) -> int:
        i, j = manager.IndexToNode(from_index), manager.IndexToNode(to_index)
        return int(dist[i][j] * scale)

    transit = routing.RegisterTransitCallback(distance_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit)

    def demand_cb(from_index: int) -> int:
        return int(demands[manager.IndexToNode(from_index)] * scale)

    demand_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(
        demand_idx, 0, [int(c * scale) for c in capacities], True, "Capacity"
    )

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    params.time_limit.FromSeconds(time_limit_s)

    solution = routing.SolveWithParameters(params)
    if solution is None:
        return None

    assignments: list[list[int]] = []
    for v in range(num_vehicles):
        index = routing.Start(v)
        seq: list[int] = []
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                seq.append(node)
            index = solution.Value(routing.NextVar(index))
        assignments.append(seq)
    return assignments


def optimize(
    origin: tuple[float, float], stops: list[Stop], capacities: list[float]
) -> OptimizationResult:
    """Assign stops to vehicles under capacity and sequence each route.

    `capacities` is one entry per available vehicle (index-aligned). Raises
    InfeasibleRouteError if demand can't fit the fleet.
    """
    if not stops or not capacities:
        return OptimizationResult()

    total_demand = sum(s.demand_kg for s in stops)
    if total_demand > sum(capacities) + 1e-6:
        raise InfeasibleRouteError(
            f"Total demand {total_demand:g} kg exceeds fleet capacity "
            f"{sum(capacities):g} kg."
        )

    points = [origin, *[(s.lat, s.lng) for s in stops]]
    dist = _distance_matrix(points)
    demands = [0.0, *[s.demand_kg for s in stops]]

    naive_assign, naive_total = _naive_plan(dist, stops, capacities)

    assignments: list[list[int]] | None = None
    method = "greedy_2opt"
    if _ORTOOLS:
        assignments = _solve_ortools(dist, demands, capacities)
        if assignments is not None:
            method = "or-tools"
    if assignments is None:
        # Fallback: start from the naive assignment, improve each route with 2-opt.
        assignments = [_two_opt(dist, seq) for seq in naive_assign]

    routes: list[OptimizedVehicleRoute] = []
    total = 0.0
    for v, seq in enumerate(assignments):
        if not seq:
            continue
        d = _route_distance(dist, seq)
        total += d
        routes.append(
            OptimizedVehicleRoute(
                vehicle_index=v,
                order_ids=[stops[node - 1].order_id for node in seq],
                distance_km=round(d, 2),
            )
        )

    return OptimizationResult(
        routes=routes,
        total_distance_km=round(total, 2),
        naive_distance_km=round(naive_total, 2),
        method=method,
    )
