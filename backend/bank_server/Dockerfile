# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY backend/bank_server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory structure
COPY backend/ ./backend/

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8006

# Run the purchase agent server
CMD ["python", "-m", "backend.bank_server.server"]
