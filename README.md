# findhub-tracker

A web application that periodically retrieves the locations of devices associated with a Google Find Hub account, stores the history in PostgreSQL, and displays it on an interactive map.

> [!IMPORTANT]
> Google does not provide a public API for personal accounts. This project uses [GoogleFindMyTools](https://github.com/leonboe1/GoogleFindMyTools), an unofficial library that interacts with Google's internal endpoints and decrypts account data. Google may change the service or block the account at any time. Use it only with your own accounts and devices, follow Google's terms, and avoid frequent automated polling.

## Features

- Lists all devices associated with the authenticated account.
- Requests each device's location when the backend starts and then at a configurable interval, with a minimum of 5 minutes.
- Stores every sample in PostgreSQL, including its accuracy and the timestamp reported by Google.
- Displays the last known location of each device.
- Queries history through 1-hour, 6-hour, 24-hour, and 7-day presets, or a custom time range.
- Draws routes along roads using Valhalla and, when available, shows a faster alternative route.
- Includes a device selector, start and end markers, direction arrows, distance, duration, and polling status.
- Allows an immediate location request from the interface.

## Architecture

```text
Browser
   │
   ▼
web · React + Vite + Leaflet + nginx
   │  HTTP /api/*
   ▼
backend · FastAPI + APScheduler
   ├──► Google Find Hub, through GoogleFindMyTools
   ├──► Public Valhalla service, for road routing
   └──► PostgreSQL 16 + PostGIS
```

| Service | Host port | Description |
| --- | ---: | --- |
| `web` | `8180` | React interface and reverse proxy for `/api/*` |
| `backend` | `8000` | FastAPI API, scheduler, and Google Find Hub client |
| `db` | `5432` | PostgreSQL 16 with PostGIS |

## Technologies

- **Frontend:** React 18, TypeScript, Vite, Leaflet, and React Leaflet.
- **Backend:** Python 3.12, FastAPI, SQLAlchemy, asyncpg, and APScheduler.
- **Database:** PostgreSQL 16 + PostGIS.
- **Integrations:** GoogleFindMyTools and the public Valhalla service.
- **Deployment:** Docker Compose and nginx.

## Requirements

- Docker Engine with Docker Compose v2 (`docker compose`).
- Python 3 and `pip` on the host for initial authentication.
- Google Chrome on the host to complete sign-in.
- Git to clone GoogleFindMyTools during authentication and image builds.
- Node.js 20 and npm only if developing the frontend outside Docker.
- A Google account with at least one device registered in Find Hub.
- An internet connection during installation and operation.

## Getting started

Run these commands from the project root.

### 1. Configure the environment

On Linux or macOS:

```bash
cp .env.example .env
```

In PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` if you want to change the polling interval. Do not commit `.env`.

### 2. Authenticate the Google account

The following command clones GoogleFindMyTools into `.tools/`, installs its dependencies, and opens Chrome for sign-in:

```bash
python backend/scripts/auth.py
```

When it finishes, the script creates `auth/secrets.json`. This file contains session credentials: do not share it or commit it to git. It only needs to be generated initially and must be renewed when Google requests it or the tokens expire.

If you use a virtual environment, activate Python from that environment before running the script.

### 3. Start the services

If you will run this on a Raspberry Pi (amd64 architecture), install this:

```bash
sudo apt-get update
sudo apt-get install -y qemu-user-static binfmt-support
```

```bash
docker compose up -d --build
```

The first build downloads GoogleFindMyTools and may take a while. Data persists in the `pgdata` Docker volume.

### 4. Open the application

- Web interface: <http://localhost:8180>
- Interactive API documentation: <http://localhost:8000/docs>
- Frontend health check: <http://localhost:8180/healthz>
- Backend health check: <http://localhost:8000/api/health>

## Usage

1. Wait for the backend to complete its initial poll.
2. Select a device in the left panel.
3. Choose a time range or set custom start and end times.
4. Click **Trazar recorrido** to retrieve the history and calculate a route.
5. Click **Solicitar posición ahora** only when an immediate sample is needed.

If the backend cannot find `auth/secrets.json`, the interface displays **Autenticación pendiente**. The displayed positions are the latest locations reported by Google for each device; they do not mean the device was at that exact point when the API was queried.

## Configuration

Configuration is loaded from `.env` by `backend/app/config.py`.

| Variable | Default | Description |
| --- | --- | --- |
| `POLL_INTERVAL_MIN` | `15` | Polling interval in minutes. The backend enforces a minimum of `5`. |
| `DATABASE_URL` | `postgresql+asyncpg://tracker:tracker@db:5432/findhub` | PostgreSQL connection string. |
| `AUTH_SECRETS_PATH` | `/app/auth/secrets.json` | Path to the secrets file inside the container. |
| `API_TOKEN` | empty | Optional Bearer token that protects `/api/*`, except the health check. |
| `LOG_LEVEL` | `INFO` | Backend logging level. |

`docker-compose.yml` always defines the internal PostgreSQL connection and mounts `./auth` read-only inside the container.

### API_TOKEN

When `API_TOKEN` is set, requests must include:

```http
Authorization: Bearer <token>
```

The included interface does not send this header. If you enable `API_TOKEN`, the interface will stop retrieving data unless you modify the client or use a proxy that injects the token. Leave it empty for the intended local setup.

## API

All endpoints are under `/api`. When `API_TOKEN` is enabled, they require the Bearer header shown above.

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/status` | Scheduler, authentication, device, and latest-location status. |
| `GET` | `/api/devices` | Devices registered in the database. |
| `GET` | `/api/locations/latest` | Latest location for every device or for a specific `device_id`. |
| `GET` | `/api/locations` | History for `device_id`, optionally filtered by `from`, `to`, and `limit`. |
| `GET` | `/api/route` | Road route and alternative calculated by Valhalla. |
| `POST` | `/api/poll` | Forces an immediate polling cycle. |
| `GET` | `/api/health` | Reports whether the backend process is running. |

Example:

```bash
curl "http://localhost:8000/api/status"
```

Time filters: `from` and `to` accept ISO 8601 dates. `limit` accepts at most `50000` locations. Include a time zone, such as `2026-09-23T12:00:00Z`, to avoid ambiguity when filtering history.

## Data model

The backend automatically creates these tables when it connects:

- `devices`: identifier, name, type, and first/last-seen timestamps.
- `locations`: device, coordinates, accuracy, Google's timestamp, and polling time.

Every successful poll inserts the available locations without replacing earlier samples. There is no automatic cleanup or retention policy, so the amount of data and its disk usage grow over time.

## Local development

The recommended setup keeps PostgreSQL and FastAPI in Docker while running Vite on the host for fast frontend reloads:

```bash
docker compose up -d db backend
cd web
npm ci
npm run dev
```

Vite serves the application at <http://localhost:5173> and forwards `/api/*` requests to `http://localhost:8000`.

To verify a production frontend build:

```bash
cd web
npm run build
```

## Operations

```bash
# View backend logs
docker compose logs -f backend

# Restart after renewing authentication
docker compose restart backend

# Rebuild and recreate the services
docker compose up -d --build

# Stop the containers and preserve the data
docker compose down

# Stop the containers and also delete the PostgreSQL history
docker compose down -v
```

The last command is destructive: it deletes the `pgdata` volume and all stored history.

## Troubleshooting

### Authentication required

1. Run `python backend/scripts/auth.py` from the project root.
2. Complete sign-in in Chrome.
3. Restart the backend with `docker compose restart backend`.
4. Check `http://localhost:8000/api/health` and the backend logs.

### No locations appear

- Verify that the device is registered in Find Hub and has location sharing enabled.
- Check that the device is connected and that the account can see it in the Google Find Hub app.
- Review `docker compose logs backend` to identify authentication, network, or timeout errors.
- Each device query has a 60-second timeout; an unresponsive device does not prevent the others from being queried.

### The route does not follow roads

The backend queries a public Valhalla server with no SLA. If the service does not respond, the API returns `routed: false` and the frontend keeps a straight line between the points.

### A port is already in use

Docker Compose publishes ports `8180`, `8000`, and `5432`. If one is occupied, stop the process using it or change the left-hand side of the corresponding `ports` entry in `docker-compose.yml`.

## Privacy and security

- `auth/secrets.json` grants access to the Google session; treat it as a complete credential.
- The database contains precise location history. Protect its backups and do not publish it.
- The containers publish their ports on all host interfaces. For local-only use, bind them to `127.0.0.1`, restrict them with a firewall, or use a secure proxy.
- The application does not implement users, roles, or additional database encryption.
- Road routing sends coordinates to the public `valhalla1.openstreetmap.de` service. The interface currently provides no option to disable this request.
- There is no official personal-account API, and the internal endpoint may change without notice.

## Limitations

- There is no official API or stability guarantee for Google Find Hub.
- The interval is limited to 5 minutes, but this is a project safeguard and does not guarantee that Google will not detect or restrict the account.
- `POST /api/poll` can bypass the scheduled interval; avoid automating frequent calls.
- Only location, accuracy, and time are stored; battery, connectivity, and detailed device status are not included.
- The device is not monitored continuously in the background: the application queries Find Hub through a separate process.
- Valhalla is a shared public service and may be rate-limited or unavailable.
- There is no automatic history deletion policy.

## Project structure

```text
.
├── auth/                         # generated secrets; not versioned
├── backend/
│   ├── app/
│   │   ├── collector.py          # polling cycle
│   │   ├── config.py             # configuration
│   │   ├── db.py                 # schema and SQL queries
│   │   ├── google_find.py        # GoogleFindMyTools integration
│   │   ├── location_worker.py    # isolated query with timeout
│   │   ├── main.py               # API and scheduler
│   │   ├── routing.py            # Valhalla integration
│   │   └── schemas.py            # API models
│   ├── scripts/auth.py           # initial Chrome authentication
│   ├── postgres-init.sql         # PostGIS activation
│   ├── Dockerfile
│   └── requirements.txt
├── web/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DevicePanel.tsx   # controls and status
│   │   │   └── MapView.tsx       # map, route, and markers
│   │   ├── api.ts
│   │   ├── App.tsx
│   │   └── types.ts
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── .env.example
```
