# Use official slim Python image
FROM python:3.11-slim

# Install system dependencies (including libmagic)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port (Heroku ignores this, but good practice)
EXPOSE 8000

# Start app using Heroku-provided $PORT
CMD ["sh", "-c", "gunicorn ai_assistant.buildabot.wsgi:application --bind 0.0.0.0:$PORT"]
