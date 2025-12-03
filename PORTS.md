# Port Mappings

This document lists all port mappings for the IoT Platform services.

## Service Ports

| Service | Host Port | Container Port | Description |
|---------|-----------|----------------|-------------|
| **Backend API** | 5000 | 5000 | FastAPI ingestion gateway |
| **TCP Ingestion** | 6000 | 6000 | JSON-over-TCP telemetry |
| **PostgreSQL** | 5433 | 5432 | Database (changed from 5432 to avoid conflict) |
| **Kafka** | 29092 | 9092 | Message broker (host port changed to avoid conflict) |
| **Zookeeper** | 2181 | 2181 | Kafka coordination |
| **MQTT Broker** | 1884 | 1883 | MQTT protocol (changed from 1883 to avoid conflict) |
| **MQTT WebSockets** | 9002 | 9001 | MQTT WebSocket support |

## Notes

- **PostgreSQL**: Changed to port 5433 on host because port 5432 is already in use
- **MQTT**: Changed to port 1884 on host because port 1883 is already in use
- Internal container communication uses the container ports (e.g., backend connects to `postgres:5432`)

## Connection Strings

### From Host Machine
- Backend API: `http://localhost:5000`
- TCP Ingestion: `tcp://localhost:6000`
- PostgreSQL: `postgresql://iot_user:iot_password@localhost:5433/iot_platform`
- Kafka: `localhost:29092`
- MQTT: `localhost:1884`

### From Docker Containers (Internal Network)
- Backend API: `http://backend:5000`
- TCP Ingestion: `tcp://backend:6000`
- PostgreSQL: `postgresql://iot_user:iot_password@postgres:5432/iot_platform`
- Kafka: `kafka:9092`
- MQTT: `mqtt-broker:1883`

