import type { Device, History, LocationPoint, Route, Status } from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`${res.status} ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function getStatus(): Promise<Status> {
  return request<Status>('/api/status');
}

export function getDevices(): Promise<Device[]> {
  return request<Device[]>('/api/devices');
}

export function getLatest(deviceId?: string): Promise<LocationPoint[]> {
  const q = deviceId ? `?device_id=${encodeURIComponent(deviceId)}` : '';
  return request<LocationPoint[]>(`/api/locations/latest${q}`);
}

export function getLocations(deviceId: string, from?: string, to?: string): Promise<History> {
  const params = new URLSearchParams({ device_id: deviceId });
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  return request<History>(`/api/locations?${params.toString()}`);
}

export function getRoute(deviceId: string, from?: string, to?: string): Promise<Route> {
  const params = new URLSearchParams({ device_id: deviceId });
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  return request<Route>(`/api/route?${params.toString()}`);
}

export function pollNow(): Promise<{ status: string }> {
  return request<{ status: string }>('/api/poll', { method: 'POST' });
}