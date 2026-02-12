# ScholarBot - CSUSB Library Assistant
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for cache/logs
RUN mkdir -p /data

# Streamlit runs on 8501 by default
EXPOSE 8501

# Run Streamlit; bind to 0.0.0.0 so it's reachable from outside the container
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
