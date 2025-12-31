FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (including Java for PyReportJasper)
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    default-jre \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Render will set PORT env var)
EXPOSE 5000

# Run the application
# Use PORT env var if provided (for Render), otherwise default to 5000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-5000}"]

