# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY backend/host_agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory structure
COPY backend/ ./backend/

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the orchestrator server
CMD ["python", "-m", "backend.host_agent.server"]

