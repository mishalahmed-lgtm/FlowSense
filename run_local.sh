#!/bin/bash
# Quick script to run the application locally

set -e

echo "🚀 Starting IoT Platform Locally..."

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cat > .env << 'ENVEOF'
DATABASE_URL=postgresql://iot_user:iot_password@localhost:5433/iot_platform
ADMIN_EMAIL=admin@flowsense.com
ADMIN_PASSWORD=AdminFlow
ADMIN_JWT_SECRET=supersecretjwtkey
LOG_LEVEL=INFO
ENVEOF
    echo "✅ Created .env file. Edit it if needed."
fi

# Check if PostgreSQL is running (Docker)
if ! docker ps | grep -q iot-postgres; then
    echo "🐘 Starting PostgreSQL with Docker..."
    docker-compose up -d postgres
    echo "⏳ Waiting for PostgreSQL to be ready..."
    sleep 5
fi

# Initialize database
echo "🗄️  Initializing database..."
python init_db.py

# Run the application
echo "🎯 Starting FastAPI server..."
echo "📍 API will be available at: http://localhost:5000"
echo "📍 API docs at: http://localhost:5000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

uvicorn main:app --reload --host 0.0.0.0 --port 5000
