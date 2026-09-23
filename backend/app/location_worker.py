#!/usr/bin/env python3
"""Worker aislado para consultar la ubicación de un dispositivo de Google Find Hub.

Se ejecuta como subproceso por google_find.GoogleFindMyDevices.get_device_location
para poder imponer un timeout sin dejar hilos huérfanos (la librería espera el
push de ubicación en un loop sin límite).

Uso:
    python location_worker.py <canonic_id> <device_name>

Imprime un JSON por stdout: {coordenadas} o {error: <detalle>}.
"""

import contextlib
import io
import json
import sys
from contextlib import redirect_stdout

from app.google_find import DeviceLocation, GoogleFindMyDevices


def parse_output(output: str, canonic_id: str, device_name: str) -> DeviceLocation | None:
    return GoogleFindMyDevices._parse_location_output(output, canonic_id, device_name)


def main() -> int:
    canonic_id, device_name = sys.argv[1], sys.argv[2]

    from NovaApi.ExecuteAction.LocateTracker.location_request import (
        get_location_data_for_device,
    )

    captured = io.StringIO()
    try:
        with redirect_stdout(captured):
            get_location_data_for_device(canonic_id, device_name)
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        return 0

    loc = parse_output(captured.getvalue(), canonic_id, device_name)
    if loc is None:
        print(json.dumps({"error": "no_location"}))
        return 0

    print(
        json.dumps(
            {
                "device_id": loc.device_id,
                "device_name": loc.device_name,
                "device_type": loc.device_type,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "accuracy_meters": loc.accuracy_meters,
                "google_timestamp": loc.google_timestamp.isoformat()
                if loc.google_timestamp
                else None,
                "polled_at": loc.polled_at.isoformat(),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())