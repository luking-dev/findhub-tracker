import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .google_find import DeviceLocation

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    device_type TEXT NOT NULL DEFAULT 'unknown',
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS locations (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    name TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    accuracy_meters REAL,
    google_timestamp TIMESTAMPTZ,
    polled_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_locations_device_polled
    ON locations(device_id, polled_at ASC);

CREATE INDEX IF NOT EXISTS idx_locations_polled
    ON locations(polled_at DESC);
"""


def _row(row) -> dict:
    return dict(row._mapping)


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url)

    async def connect(self) -> None:
        async with self.engine.begin() as conn:
            for stmt in SCHEMA.strip().split(";"):
                if stmt.strip():
                    await conn.execute(text(stmt.strip()))
        log.info("esquema_bd_inicializado")

    async def close(self) -> None:
        await self.engine.dispose()

    async def register_device(
        self, device_id: str, name: str, device_type: str
    ) -> None:
        """Registra un dispositivo de la cuenta sin tocar last_seen.

        Se crea si no existe; si ya existe solo actualiza nombre/tipo (refleja
        renombres en la cuenta sin alterar la última vez con posición).
        """
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO devices (device_id, name, device_type)
                    VALUES (:id, :name, :type)
                    ON CONFLICT (device_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        device_type = EXCLUDED.device_type
                    """
                ),
                {"id": device_id, "name": name, "type": device_type},
            )

    async def upsert_device(
        self, device_id: str, name: str, device_type: str, now: datetime
    ) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO devices (device_id, name, device_type, first_seen, last_seen)
                    VALUES (:id, :name, :type, :now, :now)
                    ON CONFLICT (device_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        device_type = EXCLUDED.device_type,
                        last_seen = EXCLUDED.last_seen
                    """
                ),
                {"id": device_id, "name": name, "type": device_type, "now": now},
            )

    async def store_location(self, loc: DeviceLocation) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO locations
                        (device_id, name, latitude, longitude,
                         accuracy_meters, google_timestamp, polled_at)
                    VALUES (:id, :name, :lat, :lng, :acc, :gts, :polled)
                    """
                ),
                {
                    "id": loc.device_id,
                    "name": loc.device_name,
                    "lat": loc.latitude,
                    "lng": loc.longitude,
                    "acc": loc.accuracy_meters,
                    "gts": loc.google_timestamp,
                    "polled": loc.polled_at,
                },
            )

    async def list_devices(self) -> list[dict]:
        async with self.engine.connect() as conn:
            res = await conn.execute(
                text(
                    """SELECT device_id, name, device_type, last_seen
                       FROM devices ORDER BY name"""
                )
            )
            return [_row(r) for r in res.fetchall()]

    async def latest_location(self, device_id: str | None = None) -> list[dict]:
        async with self.engine.connect() as conn:
            if device_id:
                res = await conn.execute(
                    text(
                        """SELECT id, device_id, name, latitude, longitude,
                                  accuracy_meters, google_timestamp, polled_at
                           FROM locations WHERE device_id = :id
                           ORDER BY polled_at DESC LIMIT 1"""
                    ),
                    {"id": device_id},
                )
            else:
                res = await conn.execute(
                    text(
                        """SELECT DISTINCT ON (device_id) id, device_id, name,
                                  latitude, longitude, accuracy_meters,
                                  google_timestamp, polled_at
                           FROM locations ORDER BY device_id, polled_at DESC"""
                    )
                )
            return [_row(r) for r in res.fetchall()]

    async def history(
        self,
        device_id: str,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 10000,
    ) -> list[dict]:
        clauses = ["device_id = :id"]
        params: dict = {"id": device_id, "limit": limit}
        if since is not None:
            clauses.append("polled_at >= :since")
            params["since"] = since
        if until is not None:
            clauses.append("polled_at <= :until")
            params["until"] = until

        query = (
            """SELECT id, device_id, name, latitude, longitude,
                      accuracy_meters, google_timestamp, polled_at
               FROM locations WHERE """
            + " AND ".join(clauses)
            + " ORDER BY polled_at ASC LIMIT :limit"
        )
        async with self.engine.connect() as conn:
            res = await conn.execute(text(query), params)
            return [_row(r) for r in res.fetchall()]