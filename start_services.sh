#!/bin/bash
# Script to start Docker services and initialize the database

set -e

echo "============================================================"
echo "Starting IoT Platform Services"
echo "============================================================"

# Stop any existing containers
echo "Stopping existing containers..."
sudo docker-compose down 2>/dev/null || true

# Start all services
echo "Starting services..."
sudo docker-compose up -d

# Wait for services to be healthy
echo "Waiting for services to be ready..."
sleep 10

# Check service status
echo ""
echo "Service Status:"
sudo docker-compose ps

# Wait for PostgreSQL to be ready
echo ""
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if sudo docker exec iot-postgres pg_isready -U iot_user > /dev/null 2>&1; then
        echo "✓ PostgreSQL is ready"
        break
    fi
    echo "  Waiting... ($i/30)"
    sleep 2
done

# Initialize database
echo ""
echo "Initializing database..."
sudo docker-compose exec -T backend python init_db.py

echo ""
echo "============================================================"
echo "Services are ready!"
echo "============================================================"
echo ""
echo "Backend API: http://localhost:5000"
echo "PostgreSQL: localhost:5433 (host) -> 5432 (container)"
echo "Kafka: localhost:29092 (host) -> 9092 (container)"
echo "MQTT: localhost:1884 (host) -> 1883 (container)"
echo ""
echo "To test telemetry ingestion, get a provisioning key from the init output above"
echo "and run: python3 test_ingestion.py <provisioning_key>"

