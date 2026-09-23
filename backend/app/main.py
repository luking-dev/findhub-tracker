import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .collector import Collector
from .config import get_settings
from .db import Database
from .google_find import GoogleFindMyDevices
from .routing import route_via_osm
from .schemas import DeviceOut, HistoryOut, LocationOut, RouteOut, StatusOut

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

db: Database | None = None
collector: Collector | None = None
scheduler: AsyncIOScheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, collector, scheduler

    db = Database(settings.database_url)
    await db.connect()

    auth_dir = str(Path(settings.auth_secrets_path).parent)
    collector = Collector(db, GoogleFindMyDevices(auth_dir=auth_dir))

    interval = max(settings.poll_interval_min, 5)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        collector.poll,
        IntervalTrigger(minutes=interval),
        id="poll",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.start()
    logging.getLogger("findhub").info("programado poll cada %s min", interval)

    async def initial_poll() -> None:
        try:
            await collector.poll()
        except Exception:
            logging.getLogger("findhub").exception("error_poll_inicial")

    asyncio.create_task(initial_poll())

    yield

    if scheduler:
        scheduler.shutdown(wait=False)
    if db:
        await db.close()


app = FastAPI(title="findhub-tracker", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_token(authorization: str | None = Header(default=None)):
    if settings.api_token:
        expected = f"Bearer {settings.api_token}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Token inválido")
    return True


def get_collector() -> Collector:
    assert collector is not None
    return collector


def get_db() -> Database:
    assert db is not None
    return db


@app.get("/api/status", response_model=StatusOut, dependencies=[Depends(require_token)])
async def status():
    coll = get_collector()
    devices_raw = await get_db().list_devices()
    latest_all = {r["device_id"]: r for r in await get_db().latest_location()}

    devices = [
        DeviceOut(
            device_id=d["device_id"],
            name=d["name"],
            device_type=d["device_type"],
            last_seen=d["last_seen"],
            latest=LocationOut(**latest_all[d["device_id"]]) if d["device_id"] in latest_all else None,
        )
        for d in devices_raw
    ]

    last_poll = coll.last_poll
    return StatusOut(
        status=coll.status,
        auth_ok=coll.status != "auth_required",
        poll_interval_min=max(settings.poll_interval_min, 5),
        last_poll=last_poll,
        next_poll=last_poll + timedelta(minutes=max(settings.poll_interval_min, 5))
        if last_poll
        else None,
        last_error=coll.last_error,
        devices=devices,
    )


@app.get("/api/devices", response_model=list[DeviceOut], dependencies=[Depends(require_token)])
async def devices():
    latest_all = {r["device_id"]: r for r in await get_db().latest_location()}
    return [
        DeviceOut(
            device_id=d["device_id"],
            name=d["name"],
            device_type=d["device_type"],
            last_seen=d["last_seen"],
            latest=LocationOut(**latest_all[d["device_id"]]) if d["device_id"] in latest_all else None,
        )
        for d in await get_db().list_devices()
    ]


@app.get(
    "/api/locations/latest",
    response_model=list[LocationOut],
    dependencies=[Depends(require_token)],
)
async def locations_latest(device_id: str | None = Query(default=None)):
    rows = await get_db().latest_location(device_id)
    return [LocationOut(**r) for r in rows]


@app.get("/api/locations", response_model=HistoryOut, dependencies=[Depends(require_token)])
async def locations(
    device_id: str,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    limit: int = Query(default=10000, le=50000),
):
    rows = await get_db().history(device_id, since=from_, until=to, limit=limit)
    name = rows[0]["name"] if rows else device_id
    return HistoryOut(
        device_id=device_id,
        device_name=name,
        count=len(rows),
        points=[LocationOut(**r) for r in rows],
    )


@app.get("/api/route", response_model=RouteOut, dependencies=[Depends(require_token)])
async def route(
    device_id: str,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    limit: int = Query(default=10000, le=50000),
):
    """Recorrido por calles entre los puntos guardados (OSRM público)."""
    rows = await get_db().history(device_id, since=from_, until=to, limit=limit)
    name = rows[0]["name"] if rows else device_id

    if len(rows) < 2:
        return RouteOut(device_id=device_id, device_name=name, routed=False)

    points = [(r["latitude"], r["longitude"]) for r in rows]
    res = await asyncio.to_thread(route_via_osm, points)
    if res is None:
        return RouteOut(device_id=device_id, device_name=name, routed=False)

    return RouteOut(
        device_id=device_id,
        device_name=name,
        routed=True,
        distance_m=round(res.distance_m, 1),
        duration_s=round(res.duration_s, 1),
        coordinates=res.coordinates,
        alternative_coordinates=res.alternative_coords or [],
        alternative_distance_m=round(res.alternative_distance_m, 1)
        if res.alternative_distance_m is not None
        else None,
        alternative_duration_s=round(res.alternative_duration_s, 1)
        if res.alternative_duration_s is not None
        else None,
    )


@app.post("/api/poll", dependencies=[Depends(require_token)])
async def poll_now():
    return await get_collector().poll()


@app.get("/api/health")
async def health():
    return {"ok": True, "status": (collector.status if collector else "starting")}