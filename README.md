# IoT Platform - Data Ingestion Pipeline

Python backend service for ingesting telemetry data from IoT devices (LPG Meter, Valve Controller, GPS Tracker).

## Features

- **HTTP Telemetry Endpoint**: `/api/v1/telemetry/http` for devices using HTTP protocol
- **MQTT Integration**: Automatic ingestion from MQTT broker for valve controllers
- **TCP Telemetry Listener**: JSON-over-TCP + Dingtek DC41X hex ingestion on port `6000`
- **Device Authentication**: Provisioning key-based authentication
- **Kafka Integration**: Publishes raw telemetry to Kafka `raw_telemetry` topic
- **PostgreSQL**: Stores device metadata and provisioning keys
- **Inline Rule Engine**: Per-device rules for routing, mutation, or dropping telemetry before it hits Kafka (configurable from the admin UI)

## Architecture

```
Devices (HTTP/MQTT) → Ingestion Gateway → Kafka (raw_telemetry) → [Downstream Services]
```

## Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)
- Node.js 18+ (for the React admin console)

### Quick Start

1. **Start all services:**
   ```bash
   docker-compose up -d
   ```

2. **Initialize database with sample data:**
   ```bash
   docker-compose exec backend python init_db.py
   ```

3. **Check service health:**
   ```bash
   curl http://localhost:5000/health
   ```

### Services

- **Backend API**: http://localhost:5000
- **TCP Telemetry Socket**: `localhost:6000`
- **PostgreSQL**: `localhost:5433`
- **Kafka**: `localhost:29092`
- **MQTT Broker**: `localhost:1884`

## API Usage

### Ingest Telemetry via HTTP

```bash
curl -X POST http://localhost:5000/api/v1/telemetry/http \
  -H "Content-Type: application/json" \
  -H "X-Device-Key: <provisioning_key>" \
  -d '{
    "data": {
      "level": 75.5,
      "temperature": 25.3,
      "pressure": 1.2
    },
    "timestamp": "2024-01-15T10:30:00Z"
  }'
```

### Ingest Telemetry via TCP

Send newline-delimited JSON payloads that include `device_id`, `device_key`, and `data`. Use the helper script (`scripts/test_tcp.py`) or `nc` directly:

```bash
# Using helper script
TEST_DEVICE_ID=LPG-METER-001 TEST_DEVICE_KEY=<provisioning_key> python scripts/test_tcp.py

# Using netcat directly
cat <<'EOF' | nc localhost 6000
{"device_id":"LPG-METER-001","device_key":"<provisioning_key>","timestamp":"2024-01-15T10:30:00Z","data":{"level":72.4,"temperature":24.1}}
EOF
```

#### Dingtek DC41X hexadecimal frames

DC41X LPG level sensors send binary frames that start with `0x80` and end with `0x81`. The TCP server auto-detects these frames, decodes the payload (height, temperature, alarms, RSRP, etc.), and routes them to Kafka. To simulate an uplink frame:

```bash
TCP_HOST=127.0.0.1 TCP_PORT=6000 python scripts/test_dingtek_tcp.py
```

Set `DINGTEK_FRAME_HEX` to override the default sample frame if you have a live capture:

```bash
DINGTEK_FRAME_HEX="800001011E..." python scripts/test_dingtek_tcp.py
```

Provision a device whose `device_id` matches the BCD Device ID emitted by the sensor (e.g., `1865057042853303`). No provisioning key is required for these frames; the server authenticates them by matching the Device ID to an active record.

Every message receives a JSON acknowledgement indicating whether it was accepted, rejected, or failed.

### Get Provisioning Keys

After running `init_db.py`, provisioning keys are printed to console. You can also query the database:

```sql
SELECT d.device_id, pk.key 
FROM devices d 
JOIN provisioning_keys pk ON d.id = pk.device_id;
```

## Development

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

### Project Structure

```
.
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration settings
├── database.py             # Database connection and session
├── models.py              # SQLAlchemy models
├── auth.py                # Device authentication
├── kafka_producer.py      # Kafka producer for telemetry
├── mqtt_client.py         # MQTT client for valve controllers
├── tcp_server.py          # TCP ingestion server for JSON-over-TCP devices
├── routers/admin.py       # Admin APIs for the React console
├── routers/
│   └── telemetry.py       # Telemetry ingestion endpoints
├── frontend/              # React admin console (login + device management)
├── init_db.py             # Database initialization script
├── requirements.txt       # Python dependencies
└── docker-compose.yml     # Docker services configuration
```

## Device Types

1. **LPG Meter** (HTTP): Ultrasonic LPG Meter via NB-IoT
2. **Valve Controller** (MQTT): NB-IoT Valve Controller
3. **GPS Tracker** (HTTP): Truck GPS/Verification Device

## Rule Engine

Every device can own an ordered list of rules that run synchronously inside the ingestion handlers (HTTP, MQTT, TCP). A rule is a JSON document with:

- `condition`: comparisons against `payload.*`, `metadata.*`, or `device.*` fields supporting operators such as `>`, `<`, `==`, `in`, `contains`, etc.
- `action`:
  - `{"type": "route", "topic": "alerts.high_temp"}` → publish to a different Kafka topic
  - `{"type": "drop", "reason": "Too hot"}` → skip Kafka entirely
  - `{"type": "mutate", "set": {"payload.status": "ALERT"}}` → patch payload/metadata before publish
  - `stop` (default `true`) controls whether rule evaluation continues after the action runs.

### Managing rules

- **API:**  
  - List: `GET /api/v1/admin/devices/{device_id}/rules`  
  - Create: `POST /api/v1/admin/devices/{device_id}/rules`  
  - Update: `PUT /api/v1/admin/devices/{device_id}/rules/{rule_id}`  
  - Delete: `DELETE /api/v1/admin/devices/{device_id}/rules/{rule_id}`
- **Admin UI:** open any device → `Add Device` panel → “Rule Engine” card to add/edit JSON rules from the browser.

Matched rules are logged via `/metrics` (`rules.matches`, `rules.actions`) so you can confirm which rule fired.

## Next Steps

- Parser & Normalizer service (subscribes to `raw_telemetry` topic)
- Command Execution service
- Telemetry Storage service (writes to InfluxDB/IoTDB)
- Extend admin UI for downlink command management / richer analytics

## Admin Console (React)

1. Copy `.env.example` to `.env` inside `frontend/` and update `VITE_API_BASE_URL` if needed.
2. Install dependencies and run the dev server:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. Default admin credentials come from environment variables in `config.py` (`ADMIN_EMAIL`, `ADMIN_PASSWORD`). Update them in `.env` before deploying.

