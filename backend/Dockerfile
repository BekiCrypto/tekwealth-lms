# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that might be needed (e.g., for psycopg2)
# This step might vary based on your Python package requirements.
# For psycopg2-binary, it often includes precompiled binaries, but if using psycopg2 (source),
# you'd need build tools and libpq-dev. Slim images might require these more often.
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     libpq-dev \
#     && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group for security (optional but good practice)
# RUN addgroup --system app && adduser --system --group app

# Copy the requirements file into the container at /app
COPY ./requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code into the container at /app
# This includes your main app, alembic, models, routes, etc.
COPY . /app

# Set the user for the application (if created one)
# USER app

# Expose the port the app runs on
# This should match the port Uvicorn is configured to use.
EXPOSE 8000

# Define the command to run the application
# This command runs Uvicorn, pointing to your FastAPI app instance.
# Ensure 'backend.main:app' correctly points to your FastAPI app instance.
# If your Dockerfile is in /app/backend and main.py is in /app/backend/main.py,
# and the WORKDIR is /app, then the path to app would be 'backend.main:app'.
# If WORKDIR was /app/backend, then it would be 'main:app'.
# Given WORKDIR /app and COPY . /app (where . is backend/ from context), it becomes backend.main:app.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
