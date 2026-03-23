FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (optional but useful for psycopg binary wheels, curl for debugging)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv and project dependencies (locked)
RUN python -m pip install --no-cache-dir -U pip uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code last to leverage Docker layer cache
COPY . .

# Run as non-root
RUN useradd -m -u 10001 appuser
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs
USER appuser

EXPOSE 4500

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4500"]

