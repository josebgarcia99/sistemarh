"""Métricas de las solicitudes atendidas por este proceso.

Contadores en memoria, sin dependencias externas: cuántas solicitudes llegaron
a cada ruta, cuántas fallaron y cuánto tardaron. Se reinician al reiniciar el
proceso y son de este proceso (con varios procesos de la API, cada uno lleva
los suyos). No guardan datos de personas: la clave es la ruta declarada
(``/vacancies/{vacancy_id}``), nunca la dirección real con sus identificadores.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

# Límites superiores de cada franja de duración, en milisegundos.
BUCKETS_MS = (100, 300, 1000, 3000)
UNROUTED = "(sin ruta)"


@dataclass
class _RouteStats:
    count: int = 0
    client_errors: int = 0
    server_errors: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    buckets: list[int] = field(default_factory=lambda: [0] * (len(BUCKETS_MS) + 1))


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self._routes: dict[tuple[str, str], _RouteStats] = {}

    def record(self, method: str, route: str, status: int, duration_ms: float) -> None:
        with self._lock:
            stats = self._routes.setdefault((method, route), _RouteStats())
            stats.count += 1
            stats.client_errors += 400 <= status < 500
            stats.server_errors += status >= 500
            stats.total_ms += duration_ms
            stats.max_ms = max(stats.max_ms, duration_ms)
            index = next(
                (i for i, limit in enumerate(BUCKETS_MS) if duration_ms <= limit), len(BUCKETS_MS)
            )
            stats.buckets[index] += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            routes = [
                {
                    "method": method,
                    "route": route,
                    "count": stats.count,
                    "client_errors": stats.client_errors,
                    "server_errors": stats.server_errors,
                    "average_ms": round(stats.total_ms / stats.count, 1),
                    "max_ms": round(stats.max_ms, 1),
                    "buckets": list(stats.buckets),
                }
                for (method, route), stats in self._routes.items()
            ]
            uptime = time.monotonic() - self._started
        routes.sort(key=lambda row: (-int(row["count"]), str(row["route"]), str(row["method"])))
        return {
            "uptime_seconds": round(uptime),
            "requests": sum(int(row["count"]) for row in routes),
            "server_errors": sum(int(row["server_errors"]) for row in routes),
            "bucket_limits_ms": list(BUCKETS_MS),
            "routes": routes,
        }
