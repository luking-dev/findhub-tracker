import { useCallback, useEffect, useState } from 'react';
import DevicePanel, { type Preset } from './components/DevicePanel';
import MapView from './components/MapView';
import { getLocations, getRoute, getStatus, pollNow } from './api';
import type { LocationPoint, Status } from './types';

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInput(v: string): string {
  return v ? new Date(v).toISOString() : '';
}

function emptyRoute() {
  return {
    deviceId: '',
    points: [] as LocationPoint[],
    coords: [] as [number, number][],
    routed: false,
    distanceM: null as number | null,
    durationS: null as number | null,
    altCoords: [] as [number, number][],
    altDistanceM: null as number | null,
    altDurationS: null as number | null,
  };
}

export default function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [from, setFrom] = useState(() => toLocalInput(new Date(Date.now() - 24 * 3600 * 1000)));
  const [to, setTo] = useState(() => toLocalInput(new Date()));
  const [route, setRoute] = useState<{
    deviceId: string;
    points: LocationPoint[];
    coords: [number, number][];
    routed: boolean;
    distanceM: number | null;
    durationS: number | null;
    altCoords: [number, number][];
    altDistanceM: number | null;
    altDurationS: number | null;
  }>(emptyRoute);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [focusTick, setFocusTick] = useState(0);

  const refreshStatus = useCallback(async () => {
    try {
      const st = await getStatus();
      setStatus(st);
      setSelectedId((cur) => cur || st.devices[0]?.device_id || '');
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    refreshStatus();
    const id = setInterval(refreshStatus, 30000);
    return () => clearInterval(id);
  }, [refreshStatus]);

  const query = useCallback(
    async (deviceId?: string, fromIso?: string, toIso?: string) => {
      const id = deviceId ?? selectedId;
      if (!id) return;
      setBusy(true);
      setError('');
      setFocusTick(0);
      setRoute(emptyRoute());
      try {
        const [h, r] = await Promise.all([
          getLocations(id, fromIso, toIso),
          getRoute(id, fromIso, toIso),
        ]);
        setRoute({
          deviceId: id,
          points: h.points,
          coords: r.coordinates,
          routed: r.routed,
          distanceM: r.distance_m,
          durationS: r.duration_s,
          altCoords: r.alternative_coordinates,
          altDistanceM: r.alternative_distance_m,
          altDurationS: r.alternative_duration_s,
        });
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [selectedId],
  );

  const applyPreset = (p: Preset) => {
    const hours = p === '1h' ? 1 : p === '6h' ? 6 : p === '24h' ? 24 : 168;
    const now = Date.now();
    setFrom(toLocalInput(new Date(now - hours * 3600 * 1000)));
    setTo(toLocalInput(new Date(now)));
  };

  const selectDevice = (id: string) => {
    setSelectedId(id);
    setFocusTick(0);
    setRoute(emptyRoute());
  };

  const clearRoute = () => {
    setFocusTick(0);
    setRoute(emptyRoute());
  };

  const handlePoll = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await pollNow();
      const st = await getStatus();
      setStatus(st);
      if (res.status === 'ok' || res.status === 'no_data') {
        setFocusTick((t) => t + 1);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const polyPoints = route.deviceId === selectedId ? route.points : [];
  const routeLine = route.deviceId === selectedId ? route.coords : [];
  const routeRouted = route.deviceId === selectedId && route.routed;
  const routeDistanceM = routeRouted ? route.distanceM : null;
  const routeDurationS = routeRouted ? route.durationS : null;
  const routeAltLine = route.deviceId === selectedId ? route.altCoords : [];
  const routeAltDistanceM = routeRouted ? route.altDistanceM : null;
  const routeAltDurationS = routeRouted ? route.altDurationS : null;

  return (
    <div className="layout">
      <aside className="panel">
        <DevicePanel
          status={status}
          selectedId={selectedId}
          from={from}
          to={to}
          onSelectDevice={selectDevice}
          onFromChange={setFrom}
          onToChange={setTo}
          onPreset={applyPreset}
          onQuery={() => query(selectedId, fromLocalInput(from), fromLocalInput(to))}
          onClear={clearRoute}
          onPollNow={handlePoll}
          busy={busy}
        />
        {error && <div className="error-box">{error}</div>}
      </aside>
      <main className="map-wrap">
        <MapView
          devices={status?.devices ?? []}
          points={polyPoints}
          selectedId={selectedId}
          focusTick={focusTick}
          routeLine={routeLine}
          routed={routeRouted}
          distanceM={routeDistanceM}
          durationS={routeDurationS}
          altRouteLine={routeAltLine}
          altDistanceM={routeAltDistanceM}
          altDurationS={routeAltDurationS}
        />
      </main>
    </div>
  );
}