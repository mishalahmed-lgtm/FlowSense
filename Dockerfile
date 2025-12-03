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

# Expose port
EXPOSE 5000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]

