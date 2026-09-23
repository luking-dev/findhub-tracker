"""Wrapper de GoogleFindMyTools para consultar Google Find Hub.

GoogleFindMyTools (https://github.com/leonboe1/GoogleFindMyTools) reimplementa la
API Nova/Spot interna de Google para listar dispositivos y obtener su ubicación,
descifrando los datos E2EE con la keychain de la cuenta.

La autenticación es única (Chrome + login manual) y genera auth/secrets.json.
Después el servicio corre headless sin Chrome.
"""

import contextlib
import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)

LOCATION_TIMEOUT_SEC = 60


class AuthError(Exception):
    """Falta o es inválida la autenticación de Google."""


class GoogleUnavailableError(RuntimeError):
    """GoogleFindMyTools no está instalado / no es importable."""


@dataclass
class DeviceLocation:
    device_id: str
    device_name: str
    device_type: str
    latitude: float
    longitude: float
    accuracy_meters: float | None
    google_timestamp: datetime | None
    polled_at: datetime


class GoogleFindMyDevices:
    """Interfaz a Google Find Hub vía GoogleFindMyTools (funciones síncronas)."""

    def __init__(self, auth_dir: str) -> None:
        self.auth_dir = Path(auth_dir)
        self._devices_cache: list[tuple[str, str]] | None = None
        self._cache_time: float = 0
        self._cache_ttl: float = 300
        self._gfmt_available = self._check_gfmt()

    @staticmethod
    def _check_gfmt() -> bool:
        import importlib.util

        ok = (
            importlib.util.find_spec("NovaApi") is not None
            and importlib.util.find_spec("ProtoDecoders") is not None
        )
        if not ok:
            log.warning("GoogleFindMyTools no disponible (PYTHONPATH no apunta al checkout)")
        return ok

    def _check_auth(self) -> None:
        secrets = self.auth_dir / "secrets.json"
        if not secrets.exists():
            raise AuthError(
                f"No existe {secrets}. Ejecuta scripts/auth.py (requiere Chrome) una sola vez."
            )

    def _check_available(self) -> None:
        if not self._gfmt_available:
            raise GoogleUnavailableError(
                "GoogleFindMyTools no está instalado. Reconstruye la imagen: "
                "docker compose build backend"
            )

    def list_devices(self) -> list[tuple[str, str]]:
        """Lista (nombre, canonic_id) de todos los dispositivos registrados."""
        self._check_available()
        self._check_auth()

        if self._devices_cache and (time.monotonic() - self._cache_time) < self._cache_ttl:
            return self._devices_cache

        from NovaApi.ListDevices.nbe_list_devices import request_device_list
        from ProtoDecoders.decoder import (
            get_canonic_ids,
            parse_device_list_protobuf,
        )

        device_list = parse_device_list_protobuf(request_device_list())
        devices = get_canonic_ids(device_list)
        self._devices_cache = devices
        self._cache_time = time.monotonic()
        log.info("dispositivos_listados", extra={"cantidad": len(devices)})
        return devices

    def get_device_location(self, canonic_id: str, device_name: str) -> DeviceLocation | None:
        """Solicita la ubicación actual de un dispositivo.

        Ejecuta la consulta en un subproceso propio porque GoogleFindMyTools
        espera el push de ubicación con un loop sin timeout; si el dispositivo
        no responde, el subproceso se mata a los LOCATION_TIMEOUT_SEC y se
        continúa con el siguiente.
        """
        self._check_available()
        self._check_auth()

        worker = Path(__file__).with_name("location_worker.py")
        try:
            proc = subprocess.run(
                [sys.executable, "-u", str(worker), canonic_id, device_name],
                capture_output=True,
                text=True,
                timeout=LOCATION_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            log.warning(
                "timeout_solicitando_ubicacion",
                extra={"dispositivo": device_name, "timeout_s": LOCATION_TIMEOUT_SEC},
            )
            return None

        if proc.returncode != 0:
            log.warning(
                "worker_ubicacion_fallo",
                extra={"dispositivo": device_name, "rc": proc.returncode, "stderr": proc.stderr[:200]},
            )
            return None

        try:
            data = json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            log.warning(
                "worker_ubicacion_salida_invalida",
                extra={"dispositivo": device_name, "salida": proc.stdout[:200]},
            )
            return None

        if "error" in data:
            log.warning(
                "worker_ubicacion_error",
                extra={"dispositivo": device_name, "detalle": data["error"]},
            )
            return None

        return DeviceLocation(
            device_id=data["device_id"],
            device_name=data["device_name"],
            device_type=data["device_type"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            accuracy_meters=data["accuracy_meters"],
            google_timestamp=datetime.fromisoformat(data["google_timestamp"])
            if data["google_timestamp"]
            else None,
            polled_at=datetime.fromisoformat(data["polled_at"]),
        )

    @staticmethod
    def _parse_location_output(
        output: str, canonic_id: str, device_name: str
    ) -> DeviceLocation | None:
        """Parsea la salida de consola de la librería:
        Latitude: 47.1234567
        Longitude: -122.1234567
        Time: 1711234567
        Accuracy: 25.0
        """
        lat = lng = accuracy = None
        timestamp = None

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Latitude:"):
                with contextlib.suppress(ValueError):
                    lat = float(line.split(":", 1)[1].strip())
            elif line.startswith("Longitude:"):
                with contextlib.suppress(ValueError):
                    lng = float(line.split(":", 1)[1].strip())
            elif line.startswith("Time:"):
                with contextlib.suppress(ValueError):
                    timestamp = datetime.fromtimestamp(
                        int(line.split(":", 1)[1].strip()), tz=UTC
                    )
            elif line.startswith("Accuracy:"):
                with contextlib.suppress(ValueError):
                    accuracy = float(line.split(":", 1)[1].strip())

        if lat is None or lng is None:
            log.warning(
                "no_se_parseo_ubicacion",
                extra={"dispositivo": device_name, "salida": output[:200]},
            )
            return None

        now = datetime.now(UTC)
        return DeviceLocation(
            device_id=canonic_id,
            device_name=device_name,
            device_type="unknown",
            latitude=lat,
            longitude=lng,
            accuracy_meters=accuracy,
            google_timestamp=timestamp or now,
            polled_at=now,
        )

    def get_all_locations(self) -> list[DeviceLocation]:
        """Ubicación actual de todos los dispositivos de la cuenta."""
        devices = self.list_devices()
        locations: list[DeviceLocation] = []
        for name, cid in devices:
            loc = self.get_device_location(cid, name)
            if loc:
                locations.append(loc)
        return locations