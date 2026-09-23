import { useEffect, useMemo, useRef } from 'react';
import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { Device, LocationPoint } from '../types';

function FitBounds({
  points,
  devices,
  selectedId,
  focusTick,
}: {
  points: LocationPoint[];
  devices: Device[];
  selectedId: string;
  focusTick: number;
}) {
  const map = useMap();
  const focusedTick = useRef(0);

  useEffect(() => {
    if (focusTick > 0) {
      const latest = devices.find((d) => d.device_id === selectedId)?.latest;
      if (latest && focusedTick.current !== focusTick) {
        map.setView([latest.latitude, latest.longitude], 15);
        focusedTick.current = focusTick;
      }
      return;
    }
    focusedTick.current = 0;
    const route = points.map((p) => [p.latitude, p.longitude] as [number, number]);
    const latest = devices
      .filter((d) => d.latest)
      .map((d) => [d.latest!.latitude, d.latest!.longitude] as [number, number]);
    const all = [...route, ...latest];

    if (all.length) {
      map.fitBounds(L.latLngBounds(all).pad(0.15));
    }
  }, [points, devices, selectedId, focusTick, map]);

  return null;
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

interface MapViewProps {
  points: LocationPoint[];
  devices: Device[];
  selectedId: string;
  focusTick: number;
  routeLine: [number, number][];
  routed: boolean;
  distanceM: number | null;
  durationS: number | null;
  altRouteLine: [number, number][];
  altDistanceM: number | null;
  altDurationS: number | null;
}

function fmtKm(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

interface ArrowPoint {
  lat: number;
  lng: number;
  bearing: number;
}

function haversineM(a: [number, number], b: [number, number]): number {
  const R = 6371000;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b[0] - a[0]);
  const dLng = toRad(b[1] - a[1]);
  const sinLat = Math.sin(dLat / 2);
  const sinLng = Math.sin(dLng / 2);
  const h =
    sinLat * sinLat +
    Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * sinLng * sinLng;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function bearingDeg(a: [number, number], b: [number, number]): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const toDeg = (r: number) => (r * 180) / Math.PI;
  const lat1 = toRad(a[0]);
  const lat2 = toRad(b[0]);
  const dLng = toRad(b[1] - a[1]);
  const y = Math.sin(dLng) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
  return (toDeg(Math.atan2(y, x)) + 360) % 360;
}

function interpolateOnSegment(
  a: [number, number],
  b: [number, number],
  t: number,
): [number, number] {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

function buildArrows(positions: [number, number][], spacingM: number): ArrowPoint[] {
  const arrows: ArrowPoint[] = [];
  if (positions.length < 2) return arrows;

  const segs: { d: number; from: [number, number]; to: [number, number] }[] = [];
  let total = 0;
  for (let i = 0; i < positions.length - 1; i++) {
    const from = positions[i];
    const to = positions[i + 1];
    const d = haversineM(from, to);
    if (d <= 0) continue;
    segs.push({ d, from, to });
    total += d;
  }
  if (!segs.length) return arrows;

  if (total < spacingM) {
    const mid = total / 2;
    let acc = 0;
    for (const s of segs) {
      acc += s.d;
      if (acc >= mid) {
        const t = (mid - (acc - s.d)) / s.d;
        const p = interpolateOnSegment(s.from, s.to, t);
        arrows.push({ lat: p[0], lng: p[1], bearing: bearingDeg(s.from, s.to) });
        break;
      }
    }
    return arrows;
  }

  let acc = 0;
  let arrowIdx = 1;
  for (const s of segs) {
    const segStart = acc;
    acc += s.d;
    while (acc >= arrowIdx * spacingM) {
      const t = (arrowIdx * spacingM - segStart) / s.d;
      const p = interpolateOnSegment(s.from, s.to, t);
      arrows.push({ lat: p[0], lng: p[1], bearing: bearingDeg(s.from, s.to) });
      arrowIdx++;
    }
  }
  return arrows;
}

function arrowIcon(bearing: number): L.DivIcon {
  return L.divIcon({
    className: 'route-arrow',
    html: `<svg viewBox="0 0 24 24" width="16" height="16" style="transform:rotate(${bearing}deg)"><path d="M12 2 L20 20 L12 15 L4 20 Z" fill="#38bdf8" stroke="#0f172a" stroke-width="1.5"/></svg>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
}

const ARROW_SPACING_M = 400;

export default function MapView({
  points,
  devices,
  selectedId,
  focusTick,
  routeLine,
  routed,
  distanceM,
  durationS,
  altRouteLine,
  altDistanceM,
  altDurationS,
}: MapViewProps) {
  const startIcon = useMemo(
    () =>
      L.divIcon({
        className: 'route-marker-start',
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      }),
    [],
  );

  const endIcon = useMemo(
    () =>
      L.divIcon({
        className: 'route-marker-end',
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      }),
    [],
  );

  const path = points.map((p) => [p.latitude, p.longitude] as [number, number]);
  const routedPath = routeLine.map(([lon, lat]) => [lat, lon] as [number, number]);
  const polyPositions = routed && routedPath.length > 1 ? routedPath : path;
  const altPath = altRouteLine.map(([lon, lat]) => [lat, lon] as [number, number]);
  const latestDevices = devices.filter((d) => d.latest);

  const arrows = useMemo(() => buildArrows(polyPositions, ARROW_SPACING_M), [polyPositions]);

  const arrowIconCache = useMemo(() => new Map<number, L.DivIcon>(), []);
  const getArrowIcon = (bearing: number): L.DivIcon => {
    let icon = arrowIconCache.get(bearing);
    if (!icon) {
      icon = arrowIcon(bearing);
      arrowIconCache.set(bearing, icon);
    }
    return icon;
  };

  const latestIcons = useMemo(() => {
    const icons = new Map<string, L.DivIcon>();
    for (const d of devices) {
      if (!d.latest) continue;
      const selected = d.device_id === selectedId;
      icons.set(
        d.device_id,
        L.divIcon({
          className: selected ? 'pulse-marker pulse-marker--selected' : 'latest-marker',
          iconSize: selected ? [22, 22] : [12, 12],
          iconAnchor: selected ? [11, 11] : [6, 6],
        }),
      );
    }
    return icons;
  }, [devices, selectedId]);

  return (
    <MapContainer center={[20, 0]} zoom={2} scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <FitBounds points={points} devices={devices} selectedId={selectedId} focusTick={focusTick} />

      {polyPositions.length > 1 && (
        <>
          <Polyline
            positions={polyPositions}
            pathOptions={{ color: '#0284c7', weight: 9, opacity: 0.9 }}
          />
          <Polyline positions={polyPositions} pathOptions={{ color: '#38bdf8', weight: 6 }} />
        </>
      )}

      {routed && altPath.length > 1 && (
        <Polyline
          positions={altPath}
          pathOptions={{ color: '#38bdf8', weight: 5, opacity: 0.3 }}
        />
      )}

      {arrows.map((a, i) => (
        <Marker key={i} position={[a.lat, a.lng]} icon={getArrowIcon(a.bearing)} interactive={false} />
      ))}

      {routed && distanceM != null && (
        <div className="map-tip">
          Ruta por calles · {fmtKm(distanceM)}
          {durationS != null && ` · ${Math.round(durationS / 60)} min`}
          {altDistanceM != null && (
            <>
              <br />
              Alternativa · {fmtKm(altDistanceM)}
              {altDurationS != null && ` · ${Math.round(altDurationS / 60)} min`}
            </>
          )}
        </div>
      )}

      {points.map((p) => (
        <CircleMarker
          key={p.id}
          center={[p.latitude, p.longitude]}
          radius={3}
          pathOptions={{ color: '#38bdf8', fillColor: '#38bdf8', fillOpacity: 0.9 }}
        >
          <Tooltip>
            <span className="coord">
              {fmtTime(p.polled_at)}
              <br />
              {p.latitude.toFixed(6)}, {p.longitude.toFixed(6)}
              {p.accuracy_meters != null && (
                <>
                  <br />
                  ±{Math.round(p.accuracy_meters)} m
                </>
              )}
            </span>
          </Tooltip>
        </CircleMarker>
      ))}

      {points.length > 0 && (
        <Marker position={[points[0].latitude, points[0].longitude]} icon={startIcon}>
          <Tooltip permanent={false}>Inicio · {fmtTime(points[0].polled_at)}</Tooltip>
        </Marker>
      )}

      {points.length > 1 && (
        <Marker
          position={[points[points.length - 1].latitude, points[points.length - 1].longitude]}
          icon={endIcon}
        >
          <Tooltip permanent={false}>Fin · {fmtTime(points[points.length - 1].polled_at)}</Tooltip>
        </Marker>
      )}

      {latestDevices.map((d) => (
        <Marker
          key={d.device_id}
          position={[d.latest!.latitude, d.latest!.longitude]}
          icon={latestIcons.get(d.device_id)!}
        >
          <Tooltip>
            <span className="coord">
              <strong>{d.name}</strong>
              {d.device_id === selectedId && ' · seleccionado'}
              <br />
              {fmtTime(d.latest!.polled_at)}
              <br />
              {d.latest!.latitude.toFixed(6)}, {d.latest!.longitude.toFixed(6)}
              {d.latest!.accuracy_meters != null && (
                <>
                  <br />±{Math.round(d.latest!.accuracy_meters)} m
                </>
              )}
            </span>
          </Tooltip>
        </Marker>
      ))}
    </MapContainer>
  );
}