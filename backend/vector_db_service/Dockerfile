# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY backend/vector_db_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory structure
COPY backend/ ./backend/

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8004

# Run the inventory agent server
CMD ["python", "-m", "backend.vector_db_service.server"]