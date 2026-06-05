# Build context: repo root (so both shade-engine/ and backend/ are available).
# docker build -f backend/Dockerfile -t shelter-backend .

FROM python:3.11-slim

# System deps: nothing extra needed for stdlib-only shade-engine;
# psycopg[binary] bundles its own libpq.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy packages — separate COPY layers so pip install is only re-run when the
# relevant source changes, not every time any file changes.
COPY shade-engine/ ./shade-engine/
COPY backend/      ./backend/

# Install shade-engine first (no deps, fast), then the full backend stack.
RUN pip install --no-cache-dir ./shade-engine
RUN pip install --no-cache-dir ./backend
# psycopg[binary] ships its own libpq; required for the PostGIS storage path.
RUN pip install --no-cache-dir "psycopg[binary]"

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
