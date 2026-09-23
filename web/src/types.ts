export interface LocationPoint {
  id: number;
  device_id: string;
  name: string;
  latitude: number;
  longitude: number;
  accuracy_meters: number | null;
  google_timestamp: string | null;
  polled_at: string;
}

export interface Device {
  device_id: string;
  name: string;
  device_type: string;
  last_seen: string;
  latest: LocationPoint | null;
}

export interface History {
  device_id: string;
  device_name: string;
  count: number;
  points: LocationPoint[];
}

export interface Route {
  device_id: string;
  device_name: string;
  routed: boolean;
  distance_m: number | null;
  duration_s: number | null;
  coordinates: [number, number][];
  alternative_coordinates: [number, number][];
  alternative_distance_m: number | null;
  alternative_duration_s: number | null;
}

export interface Status {
  status: string;
  auth_ok: boolean;
  poll_interval_min: number;
  last_poll: string | null;
  next_poll: string | null;
  last_error: string | null;
  devices: Device[];
}