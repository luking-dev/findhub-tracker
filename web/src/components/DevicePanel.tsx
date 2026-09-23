import type { Status } from '../types';

export type Preset = '1h' | '6h' | '24h' | '7d';

interface DevicePanelProps {
  status: Status | null;
  selectedId: string;
  from: string;
  to: string;
  onSelectDevice: (id: string) => void;
  onFromChange: (v: string) => void;
  onToChange: (v: string) => void;
  onPreset: (p: Preset) => void;
  onQuery: () => void;
  onClear: () => void;
  onPollNow: () => void;
  busy: boolean;
}

function fmtWhen(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString('es-ES');
}

export default function DevicePanel({
  status,
  selectedId,
  from,
  to,
  onSelectDevice,
  onFromChange,
  onToChange,
  onPreset,
  onQuery,
  onClear,
  onPollNow,
  busy,
}: DevicePanelProps) {
  const lastPoll = status?.last_poll ? new Date(status.last_poll) : null;
  const stale = lastPoll && Date.now() - lastPoll.getTime() > 30 * 60 * 1000;

  const statusClass = !status
    ? 'warn'
    : status.auth_ok
      ? stale
        ? 'warn'
        : 'ok'
      : 'error';

  return (
    <>
      <div>
        <h1>findhub-tracker</h1>
        <p className="subtitle">Histórico de posición · Google Find Hub</p>
      </div>

      <div className="card">
        <h2>Estado</h2>
        <div className="status-line">
          <span className={`dot ${statusClass}`} />
          {!status
            ? 'Conectando…'
            : status.auth_ok
              ? `Muestreo activo`
              : 'Autenticación pendiente'}
        </div>
        {!status?.auth_ok && (
          <p className="info-text">
            Ejecuta en el host: <code>python backend/scripts/auth.py</code> y reinicia el backend.
          </p>
        )}
        <div className="info-text" style={{ marginTop: 8 }}>
          <div>Último muestreo: {fmtWhen(status?.last_poll ?? null)}</div>
          <div>Próximo: {fmtWhen(status?.next_poll ?? null)}</div>
          <div>Intervalo: {status?.poll_interval_min ?? '—'} min</div>
        </div>
      </div>

      {status?.last_error && <div className="error-box">{status.last_error}</div>}

      <div className="card">
        <h2>Dispositivo</h2>
        <div className="field">
          <select value={selectedId} onChange={(e) => onSelectDevice(e.target.value)}>
            {status?.devices.length === 0 && <option value="">Sin dispositivos</option>}
            {status?.devices.map((d) => (
              <option key={d.device_id} value={d.device_id}>
                {d.latest ? d.name : `${d.name} (sin datos)`}
              </option>
            ))}
          </select>
        </div>
        <div className="info-text">Dispositivos registrados: {status?.devices.length ?? 0}</div>
      </div>

      <div className="card">
        <h2>Ventana de tiempo</h2>
        <div className="row" style={{ marginBottom: 10 }}>
          {(['1h', '6h', '24h', '7d'] as Preset[]).map((p) => (
            <button key={p} className="small" onClick={() => onPreset(p)}>
              {p}
            </button>
          ))}
        </div>
        <div className="field">
          <label>Desde</label>
          <input type="datetime-local" value={from} onChange={(e) => onFromChange(e.target.value)} />
        </div>
        <div className="field">
          <label>Hasta</label>
          <input type="datetime-local" value={to} onChange={(e) => onToChange(e.target.value)} />
        </div>
        <div className="row">
          <button
            className="primary"
            style={{ flex: 1 }}
            onClick={onQuery}
            disabled={busy || !selectedId}
          >
            {busy ? 'Consultando…' : 'Trazar recorrido'}
          </button>
          <button onClick={onClear} disabled={busy}>
            Borrar
          </button>
        </div>
      </div>

      <button style={{ width: '100%' }} onClick={onPollNow} disabled={busy}>
        Solicitar posición ahora
      </button>
    </>
  );
}