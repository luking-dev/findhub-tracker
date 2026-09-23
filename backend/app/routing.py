"""Ruteo por calles usando Valhalla (servicio público de openstreetmap.de).

Se consulta https://valhalla1.openstreetmap.de/route, gratuito y sin API key.
Es un servidor compartido (sin SLA); ante cualquier fallo se devuelve None y el
frontend vuelve a la línea recta entre puntos.

Se piden dos rutas:
  - principal:  costing=auto + options.shortest=true  -> la MÁS CORTA.
  - alternativa: costing=auto sin shortest            -> la más RÁPIDA (suele
    diferir en zonas urbanas). Se muestra como trazo traslúcido.

Referencia API: https://valhalla.github.io/valhalla/api/turn-by-turn/api-reference/
"""

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

log = logging.getLogger(__name__)

VALHALLA_URL = "https://valhalla1.openstreetmap.de/route"
VALHALLA_TIMEOUT_SEC = 20
MAX_LOCATIONS_PER_REQUEST = 10


@dataclass
class RouteResult:
    coordinates: list[list[float]]
    distance_m: float
    duration_s: float
    alternative_coords: list[list[float]] | None = None
    alternative_distance_m: float | None = None
    alternative_duration_s: float | None = None


def _decode_polyline6(encoded: str) -> list[list[float]]:
    """Decodifica polyline con precisión 1e6 (formato por defecto de Valhalla).

    Devuelve coordenadas [lon, lat].
    """
    coords: list[list[float]] = []
    if not encoded:
        return coords
    index = 0
    lat = lng = 0
    while index < len(encoded):
        for is_lat in (True, False):
            result = 0
            shift = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = result >> 1
            if result & 1:
                delta = ~delta
            if is_lat:
                lat += delta / 1e6
            else:
                lng += delta / 1e6
        coords.append([lng, lat])
    return coords


def _valhalla_request(coords: list[list[float]], shortest: bool) -> RouteResult | None:
    """Rutea coordenadas [lon, lat] en orden. Devuelve None si falla."""
    if len(coords) < 2:
        return None

    payload = {
        "locations": [{"lat": lat, "lon": lon} for lon, lat in coords],
        "costing": "auto",
        "units": "kilometers",
        "costing_options": {
            "auto": {
                "shortest": shortest,
                "disable_hierarchy_pruning": True,
            }
        },
    }
    req = urllib.request.Request(
        VALHALLA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=VALHALLA_TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        log.warning("valhalla_fallo", extra={"detalle": str(e)[:200]})
        return None

    trip = data.get("trip")
    if not trip or data.get("error_code"):
        log.warning("valhalla_error", extra={"code": data.get("error_code"), "msg": data.get("error")})
        return None

    coords_out: list[list[float]] = []
    for leg in trip.get("legs", []):
        leg_coords = _decode_polyline6(leg.get("shape", ""))
        if not leg_coords:
            continue
        if coords_out and leg_coords[0] == coords_out[-1]:
            coords_out.extend(leg_coords[1:])
        else:
            coords_out.extend(leg_coords)

    if len(coords_out) < 2:
        return None

    summary = trip.get("summary", {})
    return RouteResult(
        coordinates=coords_out,
        distance_m=summary.get("length", 0.0) * 1000,
        duration_s=summary.get("time", 0.0),
    )


def _base_points(points: list[tuple[float, float]]) -> list[list[float]]:
    return [[lon, lat] for lat, lon in points]


def _chunks(converted: list[list[float]]) -> list[list[list[float]]]:
    """Agrupa en chunks de a lo sumo 10 ubicaciones (límite del servidor), con
    el último punto de uno compartido como primero del siguiente. Asegura que el
    último chunk tenga al menos 2 puntos para poder rutearlo."""
    chunks: list[list[list[float]]] = []
    i = 0
    while i < len(converted) - 1:
        chunks.append(converted[i : i + MAX_LOCATIONS_PER_REQUEST])
        i += MAX_LOCATIONS_PER_REQUEST - 1
    return chunks


def _merge_routes(chunks: list[list[list[float]]], shortest: bool) -> RouteResult | None:
    out: list[list[float]] = []
    distance = duration = 0.0
    for idx, chunk in enumerate(chunks):
        res = _valhalla_request(chunk, shortest)
        if res is None:
            return None
        if out and res.coordinates[0] == out[-1]:
            out.extend(res.coordinates[1:])
        else:
            out.extend(res.coordinates)
        distance += res.distance_m
        duration += res.duration_s
    return RouteResult(coordinates=out, distance_m=distance, duration_s=duration)


def route_via_osm(points: list[tuple[float, float]]) -> RouteResult | None:
    """Rutea los puntos (lat, lon) en orden cronológico por las calles.

    Principal = ruta de menor distancia (shortest). Alternativa = ruta más
    rápida (distinta) cuando difiere de la principal.
    """
    if len(points) < 2:
        return None

    converted = _base_points(points)
    chunks = _chunks(converted)

    main = _merge_routes(chunks, shortest=True)
    if main is None:
        return None

    fast = _merge_routes(chunks, shortest=False)
    if fast is not None and abs(fast.distance_m - main.distance_m) > 1.0:
        main.alternative_coords = fast.coordinates
        main.alternative_distance_m = fast.distance_m
        main.alternative_duration_s = fast.duration_s

    return main