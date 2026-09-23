from datetime import datetime

from pydantic import BaseModel


class LocationOut(BaseModel):
    id: int
    device_id: str
    name: str
    latitude: float
    longitude: float
    accuracy_meters: float | None = None
    google_timestamp: datetime | None = None
    polled_at: datetime


class DeviceOut(BaseModel):
    device_id: str
    name: str
    device_type: str = "unknown"
    last_seen: datetime
    latest: LocationOut | None = None


class HistoryOut(BaseModel):
    device_id: str
    device_name: str
    count: int
    points: list[LocationOut]


class RouteOut(BaseModel):
    device_id: str
    device_name: str
    routed: bool
    distance_m: float | None = None
    duration_s: float | None = None
    coordinates: list[list[float]] = []
    alternative_coordinates: list[list[float]] = []
    alternative_distance_m: float | None = None
    alternative_duration_s: float | None = None


class StatusOut(BaseModel):
    status: str
    auth_ok: bool
    poll_interval_min: int
    last_poll: datetime | None = None
    next_poll: datetime | None = None
    last_error: str | None = None
    devices: list[DeviceOut] = []