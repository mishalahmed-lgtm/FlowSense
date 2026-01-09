FROM python:3.12-slim

WORKDIR /app

# Install only essential system dependencies (removed Java - saves ~200MB)
# Java was only needed for PyReportJasper which isn't used
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
# Use requirements-minimal.txt for faster builds (excludes heavy packages)
COPY requirements-minimal.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Render will set PORT env var)
EXPOSE 5000

# Run the application
# Use PORT env var if provided (for Render), otherwise default to 5000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-5000}"]

