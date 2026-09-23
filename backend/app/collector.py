import asyncio
import logging
from datetime import datetime, timezone

from .db import Database
from .google_find import AuthError, GoogleFindMyDevices, GoogleUnavailableError

log = logging.getLogger(__name__)


class Collector:
    """Ciclo de muestreo: consulta Google Find Hub y persiste en la BD."""

    def __init__(self, db: Database, gfm: GoogleFindMyDevices) -> None:
        self.db = db
        self.gfm = gfm
        self.last_poll: datetime | None = None
        self.last_error: str | None = None
        self.status = "unknown"
        self.devices_count = 0

    async def poll(self) -> dict:
        self.last_poll = datetime.now(timezone.utc)

        try:
            devices = await asyncio.to_thread(self.gfm.list_devices)
        except AuthError as e:
            self.status = "auth_required"
            self.last_error = str(e)
            log.warning("auth_requerida: %s", e)
            return self.snapshot()
        except GoogleUnavailableError as e:
            self.status = "error"
            self.last_error = str(e)
            log.error("googlefindmytools_no_disponible: %s", e)
            return self.snapshot()
        except Exception:
            self.status = "error"
            self.last_error = "error_interno"
            log.exception("error_ciclo_de_muestreo")
            return self.snapshot()

        for name, canonic_id in devices:
            await self.db.register_device(canonic_id, name, "unknown")

        stored = 0
        for name, canonic_id in devices:
            loc = await asyncio.to_thread(
                self.gfm.get_device_location, canonic_id, name
            )
            if loc:
                await self.db.upsert_device(
                    loc.device_id, loc.device_name, loc.device_type, self.last_poll
                )
                await self.db.store_location(loc)
                stored += 1

        self.devices_count = stored
        self.status = "ok" if stored else "no_data"
        self.last_error = None
        log.info(
            "ciclo_de_muestreo_ok",
            extra={"dispositivos": stored, "registrados": len(devices)},
        )
        return self.snapshot()

    def snapshot(self) -> dict:
        return {
            "status": self.status,
            "last_poll": self.last_poll,
            "last_error": self.last_error,
            "devices_count": self.devices_count,
        }