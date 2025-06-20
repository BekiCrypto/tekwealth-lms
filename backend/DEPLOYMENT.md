# Backend Deployment Guide

This guide provides instructions for deploying the backend application, including environment variable configuration, database migrations with Alembic, and running with Docker.

## 1. Environment Variables

The application requires several environment variables to be set for proper operation. Create a `.env` file in the `backend` directory based on the example below. **Never commit your actual `.env` file to version control.**

```env
# backend/.env.example

# Database
DATABASE_URL="postgresql://user:password@localhost:5432/mydb"

# Firebase (Service Account Key JSON file path)
# Ensure the JSON file specified here is available in your deployment environment.
# For Docker, you might need to copy it into the image or mount it as a volume.
GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/firebase-service-account-key.json"

# OpenAI API
OPENAI_API_KEY="your_openai_api_key"
OPENAI_MODEL_NAME="gpt-3.5-turbo" # Or your preferred model

# Stripe Payments
STRIPE_API_KEY="sk_your_stripe_secret_key"
STRIPE_WEBHOOK_SECRET="whsec_your_stripe_webhook_signing_secret"
# Example Stripe Price IDs (these are best managed in the SubscriptionPlan table in DB)
# STRIPE_PRICE_ID_MONTHLY="price_xxxxxxxxxxxxxx"
# STRIPE_PRICE_ID_YEARLY="price_yyyyyyyyyyyyyy"

# CORS Configuration (comma-separated origins)
CORS_ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,https://yourfrontenddomain.com"

# Logging Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL="INFO"

# Referral Commission Rates (as decimals)
COMMISSION_RATE_L1="0.10" # 10%
COMMISSION_RATE_L2="0.05" # 5%
COMMISSION_RATE_L3="0.02" # 2%

# Application Frontend URL (used in emails, etc.)
APP_FRONTEND_URL="http://localhost:3000" # Change to your actual frontend URL

# Email Server Configuration (for sending emails)
EMAIL_HOST="smtp.example.com"
EMAIL_PORT="587"
EMAIL_USERNAME="your_email_username"
EMAIL_PASSWORD="your_email_password"
EMAIL_FROM_ADDRESS="noreply@example.com"
EMAIL_FROM_NAME="Your Platform Name" # Defaults to Project Name if not set
EMAIL_USE_TLS="true" # true or false
EMAIL_USE_SSL="false" # true or false
EMAILS_TEMPLATES_DIR="backend/templates/emails" # Default path

# Uvicorn Server (defaults are usually fine, but can be set)
# HOST="0.0.0.0"
# PORT="8000"
# UVICORN_LOG_LEVEL="info"
```

## 2. Database Migrations (Alembic)

This project uses Alembic to manage database schema migrations.

### Initial Setup (if starting from scratch with an existing but empty DB)
1.  Ensure your `DATABASE_URL` in `.env` is correctly pointing to your database.
2.  The first migration has been created as a placeholder (`backend/alembic/versions/d8f2ef44275c_initial_placeholder_migration.py`).
3.  To make Alembic aware of the current schema (if tables were created by `Base.metadata.create_all()`):
    *   Run `alembic revision -m "Reflect current database schema" --autogenerate` (requires DB connection). This will generate a new migration file. Inspect it. If it correctly captures your schema, proceed.
    *   If the above autogenerate is empty because your DB already matches models perfectly AND you had an empty first migration, you might need to stamp the DB: `alembic stamp head`.

### Generating New Migrations
When you change your SQLAlchemy models (in `backend/models/`):
1.  Generate a new migration script:
    ```bash
    cd backend
    alembic revision -m "short_description_of_changes" --autogenerate
    ```
2.  Review the generated script in `backend/alembic/versions/`.
3.  Modify it if necessary (e.g., for complex data migrations, or if autogenerate missed something).

### Applying Migrations
To apply migrations to your database (upgrade to the latest revision):
```bash
cd backend
alembic upgrade head
```

### Other Alembic Commands
*   Downgrade by one revision: `alembic downgrade -1`
*   Show current revision: `alembic current`
*   Show migration history: `alembic history`

## 3. Running with Docker

A `Dockerfile` is provided in the `backend` directory to build a Docker image for the application.

### Building the Image
Navigate to the `backend` directory (where the `Dockerfile` is located) and run:
```bash
docker build -t mlm-elearning-backend .
```

### Running the Container
1.  **Using `.env` file with Docker**:
    You can pass the `.env` file to the Docker container:
    ```bash
    docker run -d -p 8000:8000 --env-file .env mlm-elearning-backend
    ```
    *   `-d`: Run in detached mode.
    *   `-p 8000:8000`: Map port 8000 of the host to port 8000 of the container.
    *   `--env-file .env`: Loads environment variables from the `.env` file (ensure paths like `GOOGLE_APPLICATION_CREDENTIALS` are valid within the container or use Docker volumes/secrets for such files).

2.  **Passing Environment Variables Individually**:
    Alternatively, pass variables directly:
    ```bash
    docker run -d -p 8000:8000 \
      -e DATABASE_URL="your_actual_db_url_accessible_from_docker" \
      -e OPENAI_API_KEY="your_openai_key" \
      # ... (and all other required environment variables) ...
      mlm-elearning-backend
    ```

### Important Notes for Docker Deployment:
*   **Database Accessibility**: Ensure the `DATABASE_URL` is accessible from within the Docker container. If your DB is running on `localhost`, the container might not be able to reach it via `localhost`. You might need to use your host machine's IP address or a Docker network alias.
*   **`GOOGLE_APPLICATION_CREDENTIALS`**: The path to the Firebase service account key must be valid *inside* the container. You might need to `COPY` this file into your Docker image (ensure `.dockerignore` doesn't exclude it if it's in the build context, and be mindful of security) or use Docker volumes or secrets management for sensitive files.
*   **Port Mapping**: The `-p host_port:container_port` maps the port. The `CMD` in the Dockerfile runs Uvicorn on port 8000 by default.

## 4. Procfile
A `Procfile` is included for platforms like Heroku or Railway:
```
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 1
```
The platform typically injects the `$PORT` environment variable. The number of workers can be adjusted.
```

This `DEPLOYMENT.md` provides a good starting point.`DEPLOYMENT.md` created in the `backend` directory.

All specified steps for the "Prepare Backend for Deployment" subtask are now complete:
1.  **Alembic**: Initialized, configured `alembic.ini` (comment for URL) and `env.py` (to load models and DB URL from config). An initial empty migration was created.
2.  **Dockerfile**: Created `backend/Dockerfile` using a Python slim image, installing requirements, copying the app, exposing the port, and setting the CMD for Uvicorn.
3.  **Procfile**: Created `backend/Procfile` for Heroku/Railway style deployments.
4.  **.gitignore**: Updated `backend/.gitignore` to include Alembic cache files.
5.  **Documentation**: Created `backend/DEPLOYMENT.md` detailing environment variables, Alembic usage, and Docker commands.

I am now ready to submit the report.
