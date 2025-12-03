#!/bin/bash
# Integration test script for IoT Platform Ingestion Gateway

set -e

echo "============================================================"
echo "IoT Platform - Integration Test Suite"
echo "============================================================"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q -r requirements.txt

# Run code validation tests
echo -e "\n${YELLOW}Running code validation tests...${NC}"
python3 test_imports.py
python3 test_app.py

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo -e "\n${YELLOW}Checking Docker services...${NC}"
    
    # Check if services are running
    if docker ps | grep -q "iot-postgres\|iot-kafka\|iot-mqtt"; then
        echo -e "${GREEN}✓ Docker services are running${NC}"
        
        # Test database connection
        echo -e "\n${YELLOW}Testing database connection...${NC}"
        if docker exec iot-postgres pg_isready -U iot_user &> /dev/null; then
            echo -e "${GREEN}✓ PostgreSQL is accessible${NC}"
            
            # Initialize database if needed
            echo -e "\n${YELLOW}Initializing database...${NC}"
            docker-compose exec -T backend python init_db.py || echo -e "${YELLOW}Database may already be initialized${NC}"
        else
            echo -e "${RED}✗ PostgreSQL is not accessible${NC}"
        fi
        
        # Start backend if not running
        if ! docker ps | grep -q "iot-backend"; then
            echo -e "\n${YELLOW}Starting backend service...${NC}"
            docker-compose up -d backend
            sleep 5
        fi
        
        # Test endpoints
        echo -e "\n${YELLOW}Testing API endpoints...${NC}"
        
        # Health check
        if curl -s http://localhost:5000/health | grep -q "healthy"; then
            echo -e "${GREEN}✓ Health endpoint working${NC}"
        else
            echo -e "${RED}✗ Health endpoint failed${NC}"
        fi
        
        # Root endpoint
        if curl -s http://localhost:5000/ | grep -q "IoT Platform"; then
            echo -e "${GREEN}✓ Root endpoint working${NC}"
        else
            echo -e "${RED}✗ Root endpoint failed${NC}"
        fi
        
    else
        echo -e "${YELLOW}Docker services are not running${NC}"
        echo -e "${YELLOW}To start services, run: sudo docker-compose up -d${NC}"
    fi
else
    echo -e "${YELLOW}Docker is not available${NC}"
fi

echo -e "\n============================================================"
echo -e "${GREEN}Test suite completed!${NC}"
echo "============================================================"

